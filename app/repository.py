"""Storage access for mocked Zoho records.

Records live in one generic SQLite table keyed by module. Filtering and sorting
happen in Python because the payloads are JSON and the dataset is mock-sized.
"""

from collections.abc import Callable
from typing import Any

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Record
from app.utils import new_record_id, now_iso

Predicate = Callable[[dict[str, Any]], bool]


def all_records(session: Session, module: str) -> list[Record]:
    stmt = select(Record).where(Record.module == module)
    return list(session.scalars(stmt))


def get(session: Session, module: str, record_id: str) -> Record | None:
    stmt = select(Record).where(Record.module == module, Record.id == str(record_id))
    return session.scalars(stmt).first()


def exists(session: Session, module: str, record_id: str) -> bool:
    return get(session, module, record_id) is not None


def make_resolver(session: Session) -> Callable[[str, str], dict[str, Any] | None]:
    def resolver(module: str, record_id: str) -> dict[str, Any] | None:
        record = get(session, module, record_id)
        return record.to_zoho() if record else None

    return resolver


def _sort_key(payload: dict[str, Any], field: str) -> tuple[int, str]:
    value = payload.get(field)
    if value is None:
        return (1, "")
    if isinstance(value, dict):
        value = value.get("name") or value.get("id") or ""
    if isinstance(value, bool):
        return (0, str(int(value)))
    if isinstance(value, (int, float)):
        return (0, f"{value:0>30.6f}")
    return (0, str(value).lower())


def query(
    session: Session,
    module: str,
    *,
    predicate: Predicate | None = None,
    sort_by: str = "Modified_Time",
    sort_order: str = "desc",
    modified_since: str | None = None,
) -> list[dict[str, Any]]:
    payloads = [record.to_zoho() for record in all_records(session, module)]

    if modified_since:
        payloads = [p for p in payloads if p.get("Modified_Time", "") > modified_since]
    if predicate is not None:
        payloads = [p for p in payloads if predicate(p)]

    payloads.sort(key=lambda p: _sort_key(p, sort_by), reverse=sort_order.lower() == "desc")
    return payloads


def paginate(
    payloads: list[dict[str, Any]], page: int, per_page: int
) -> tuple[list[dict[str, Any]], bool]:
    start = (page - 1) * per_page
    window = payloads[start : start + per_page]
    more_records = len(payloads) > start + per_page
    return window, more_records


def project(payloads: list[dict[str, Any]], fields: list[str] | None) -> list[dict[str, Any]]:
    if not fields:
        return payloads
    keep = set(fields) | {"id"}
    return [{k: v for k, v in payload.items() if k in keep} for payload in payloads]


def create(session: Session, module: str, data: dict[str, Any], record_id: str | None = None) -> Record:
    timestamp = now_iso()
    record = Record(
        id=str(record_id) if record_id else new_record_id(),
        module=module,
        data=data,
        created_time=timestamp,
        modified_time=timestamp,
    )
    session.add(record)
    session.flush()
    return record


def update(session: Session, record: Record, data: dict[str, Any]) -> Record:
    record.data = {**record.data, **data}
    record.modified_time = now_iso()
    session.add(record)
    session.flush()
    return record


def delete(session: Session, module: str, record_id: str) -> bool:
    record = get(session, module, record_id)
    if record is None:
        return False
    session.delete(record)
    session.flush()
    return True


def clear_module(session: Session, module: str) -> int:
    result = session.execute(sa_delete(Record).where(Record.module == module))
    return int(result.rowcount or 0)


def clear_all(session: Session) -> None:
    session.execute(sa_delete(Record))


def counts(session: Session) -> dict[str, int]:
    tally: dict[str, int] = {}
    for record in session.scalars(select(Record)):
        tally[record.module] = tally.get(record.module, 0) + 1
    return tally
