"""`POST /crm/v3/coql` — a practical subset of Zoho's query language."""

import re
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Response
from fastapi.responses import JSONResponse

from app.api.deps import SessionDep, _scope_covers_module
from app.api.filters import parse_coql_where
from app.auth.dependency import require_token
from app.auth.tokens import token_store
from app.modules.registry import resolve_module
from app.repository import project, query
from app.schemas.zoho import COQLPayload, ZohoAPIError

router = APIRouter(tags=["Search"], dependencies=[Depends(require_token)])

QUERY_PATTERN = re.compile(
    r"^\s*select\s+(?P<fields>.+?)"
    r"\s+from\s+(?P<module>[\w.]+)"
    r"(?:\s+where\s+(?P<where>.+?))?"
    r"(?:\s+group\s+by\s+(?P<group_by>[\w.,\s]+?))?"
    r"(?:\s+order\s+by\s+(?P<order_field>[\w.]+)(?:\s+(?P<order_dir>asc|desc))?)?"
    r"(?:\s+limit\s+(?P<limit_clause>[^;]+?))?"
    r"\s*$",
    re.IGNORECASE | re.DOTALL,
)

MAX_COQL_FIELDS = 50
MAX_COQL_LIMIT = 200

COQL_EXAMPLES = {
    "open_high_priority": {
        "summary": "Open, high priority cases",
        "value": {
            "select_query": (
                "select Subject, Status, Priority, Customer_Name from Cases "
                "where (Status = 'Open' and Priority = 'High') "
                "order by Modified_Time desc limit 50"
            )
        },
    },
    "visits_for_case": {
        "summary": "Visits belonging to one case",
        "value": {
            "select_query": (
                "select Name, Visit_Date, Status, Technician from Visits "
                "where Case = '4876000000200001' limit 100"
            )
        },
    },
    "labor_over_threshold": {
        "summary": "Labor lines above a cost threshold",
        "value": {"select_query": "select Name, Total_Cost from Labor_Costs where Total_Cost > 200"},
    },
    "paginated": {
        "summary": "Paginated query with offset, limit (Zoho syntax)",
        "value": {
            "select_query": "select Subject, Status from Cases order by Modified_Time desc limit 0, 10"
        },
    },
}


def _parse_limit_clause(raw: str | None) -> tuple[int, int]:
    """Parse LIMIT clause. Supports both `LIMIT n` and `LIMIT offset, limit` (Zoho syntax)."""
    if not raw:
        return 0, MAX_COQL_LIMIT

    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) == 1:
        return 0, int(parts[0])
    if len(parts) == 2:
        return int(parts[0]), int(parts[1])
    raise ZohoAPIError("INVALID_QUERY", "LIMIT clause must have 1 or 2 values", {"limit_clause": raw})


@router.post(
    "/coql",
    summary="Run a COQL query",
    description=(
        "Supported grammar: `SELECT <fields> FROM <Module> [WHERE <conditions>] "
        "[GROUP BY <fields>] [ORDER BY <field> asc|desc] [LIMIT ...]`.\n\n"
        "LIMIT supports two forms: `LIMIT n` (simple) or `LIMIT offset, limit` (Zoho pagination syntax). "
        "Max LIMIT is 200, max 50 fields in SELECT.\n\n"
        "WHERE supports `= != > >= < <= like, not like, in, not in, between, is null, is not null`, "
        "grouped with `and` / `or` and parentheses.\n\n"
        "**Returns HTTP 204 when the query matches nothing.**"
    ),
)
def run_coql(
    session: SessionDep,
    payload: Annotated[COQLPayload, Body(openapi_examples=COQL_EXAMPLES)],
    access_token: Annotated[str, Depends(require_token)],
) -> Response:
    match = QUERY_PATTERN.match(payload.select_query.strip())
    if not match:
        raise ZohoAPIError(
            "INVALID_QUERY",
            "unable to parse select_query",
            {"select_query": payload.select_query},
        )

    module = resolve_module(match.group("module"))
    if module is None:
        raise ZohoAPIError(
            "INVALID_MODULE",
            "the module name given seems to be invalid",
            {"module": match.group("module")},
        )

    issued = token_store.get(access_token)
    if issued and not _scope_covers_module(issued.scope, module.api_name):
        raise ZohoAPIError(
            "OAUTH_SCOPE_MISMATCH",
            "invalid oauth scope to access this URL",
            {"scope": issued.scope, "module": module.api_name},
        )

    raw_fields = [f.strip() for f in match.group("fields").split(",") if f.strip()]
    fields = None if raw_fields == ["*"] else raw_fields

    if fields is not None and len(fields) > MAX_COQL_FIELDS:
        raise ZohoAPIError(
            "LIMIT_EXCEEDED",
            f"maximum number of fields allowed is {MAX_COQL_FIELDS}",
            {"given": len(fields)},
        )

    known = set(module.field_map()) | {"id", "Created_Time", "Modified_Time"}
    unknown = [f for f in (fields or []) if f not in known]
    if unknown:
        raise ZohoAPIError("INVALID_QUERY", f"invalid field(s): {', '.join(unknown)}", {"fields": unknown})

    where = match.group("where")
    predicate = parse_coql_where(where) if where else None

    offset, limit = _parse_limit_clause(match.group("limit_clause"))
    if limit > MAX_COQL_LIMIT:
        raise ZohoAPIError("INVALID_QUERY", f"LIMIT cannot exceed {MAX_COQL_LIMIT}", {"limit": limit})

    payloads = query(
        session,
        module.api_name,
        predicate=predicate,
        sort_by=match.group("order_field") or "Modified_Time",
        sort_order=(match.group("order_dir") or "desc").lower(),
    )

    window = payloads[offset : offset + limit]
    if not window:
        return Response(status_code=204)

    return JSONResponse(
        status_code=200,
        content={
            "data": project(window, fields),
            "info": {"count": len(window), "more_records": len(payloads) > offset + limit},
        },
    )
