"""Zoho CRM record CRUD: list, get, insert, update, upsert, delete."""

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Path, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import (
    FieldsDep,
    ModifiedSinceDep,
    ModuleDep,
    PaginationDep,
    RequiredFieldsDep,
    SessionDep,
    parse_id_list,
    validate_record_id,
)
from app.auth.dependency import require_token
from app.config import settings
from app.modules.registry import ModuleSpec
from app.modules.validation import FieldError, validate_payload
from app.repository import (
    create,
    delete,
    get,
    make_resolver,
    paginate,
    project,
    query,
    update,
)
from app.schemas.zoho import (
    RecordsPayload,
    ZohoAPIError,
    delete_success,
    error_result,
    record_list_body,
    success_result,
    write_body,
)

router = APIRouter(tags=["Records"], dependencies=[Depends(require_token)])

CREATE_EXAMPLES = {
    "case": {
        "summary": "Create a repair case",
        "value": {
            "data": [
                {
                    "Subject": "AC unit not cooling",
                    "Status": "Open",
                    "Priority": "High",
                    "Case_Type": "Repair",
                    "Customer_Name": "Dana Levi",
                    "Phone": "+972-52-555-0111",
                    "Serial_Number": "TAD-AC-88213",
                    "Warranty_Status": "In Warranty",
                }
            ],
            "trigger": [],
        },
    },
    "visit": {
        "summary": "Create a visit linked to a case",
        "value": {
            "data": [
                {
                    "Name": "Visit #1 - diagnostic",
                    "Case": {"id": "4876000000200001"},
                    "Visit_Date": "2026-09-11T09:00:00+08:00",
                    "Status": "Scheduled",
                    "Visit_Type": "Diagnostic",
                    "Technician": "Yossi Bar",
                }
            ]
        },
    },
}

UPDATE_EXAMPLES = {
    "close_case": {
        "summary": "Close a case (id required in each record)",
        "value": {
            "data": [
                {
                    "id": "4876000000200001",
                    "Status": "Closed",
                    "Resolution": "Replaced capacitor, unit cooling normally",
                }
            ]
        },
    }
}


def _auto_fields(module: ModuleSpec, data: dict[str, Any], session: Session) -> dict[str, Any]:
    if module.api_name == "Cases" and not data.get("Case_Number"):
        existing = len(query(session, "Cases")) + 1
        data["Case_Number"] = f"CASE-{existing:05d}"
    return data


def _guard_batch_size(records: list[dict[str, Any]]) -> None:
    if not records:
        raise ZohoAPIError(
            "REQUIRED_PARAM_MISSING",
            "the data key is missing or empty",
            {"param": "data"},
        )
    if len(records) > settings.max_records_per_write:
        raise ZohoAPIError(
            "LIMIT_EXCEEDED",
            f"maximum number of records allowed is {settings.max_records_per_write}",
            {"given": len(records)},
        )


def _write_status(results: list[dict[str, Any]], success_status: int) -> int:
    successes = sum(1 for r in results if r.get("status") == "success")
    if successes == len(results):
        return success_status
    if successes == 0:
        return 400
    return 207


@router.get(
    "/{module}",
    summary="List records",
    description=(
        "Returns `{\"data\": [...], \"info\": {...}}`. **Returns HTTP 204 with an empty body when "
        "no records match** — same as the real API, and a classic client-side bug source."
    ),
)
def list_records(
    module: ModuleDep,
    session: SessionDep,
    pagination: PaginationDep,
    fields: FieldsDep,
    if_modified_since: ModifiedSinceDep,
    sort_by: Annotated[str, Query(description="Field API name to sort on (mock extension, not in real Zoho)", example="Modified_Time")] = "Modified_Time",
    sort_order: Annotated[str, Query(description="Sort order: asc or desc", example="desc")] = "desc",
    ids: Annotated[str | None, Query(description="Comma separated record ids to filter on", example="4876000000200001,4876000000200002")] = None,
) -> Response:
    page, per_page = pagination
    wanted = set(parse_id_list(ids))

    if sort_order not in ("asc", "desc"):
        raise ZohoAPIError(
            "PATTERN_NOT_MATCHED",
            "Please check whether the input values are correct",
            {"api_name": "sort_order", "given": sort_order},
        )

    payloads = query(
        session,
        module.api_name,
        predicate=(lambda p: p["id"] in wanted) if wanted else None,
        sort_by=sort_by,
        sort_order=sort_order,
        modified_since=if_modified_since,
    )

    window, more_records = paginate(payloads, page, per_page)
    if not window:
        if if_modified_since:
            return Response(status_code=304)
        return Response(status_code=204)

    return JSONResponse(
        status_code=200,
        content=record_list_body(project(window, fields), page, per_page, more_records),
    )


@router.get(
    "/{module}/{record_id}",
    summary="Get a single record",
    description="Returns `{\"data\": [record]}`, or **HTTP 404** with `RESOURCE_NOT_FOUND` when the id does not exist.",
)
def get_record(
    module: ModuleDep,
    record_id: Annotated[str, Path(description="19-digit record ID", example="4876000000200001")],
    session: SessionDep,
    fields: FieldsDep,
) -> Response:
    validate_record_id(record_id)
    record = get(session, module.api_name, record_id)
    if record is None:
        raise ZohoAPIError("RESOURCE_NOT_FOUND", "the record does not exist", {"id": record_id})
    return JSONResponse(
        status_code=200,
        content={"data": project([record.to_zoho()], fields)},
    )


@router.post(
    "/{module}",
    summary="Insert records",
    status_code=201,
    description=(
        "Accepts up to 100 records. Each record gets its own result entry, so partial success "
        "is reported per record. HTTP 201 when at least one record succeeds, 400 when all fail."
    ),
)
def insert_records(
    module: ModuleDep,
    session: SessionDep,
    payload: Annotated[RecordsPayload, Body(openapi_examples=CREATE_EXAMPLES)],
) -> JSONResponse:
    _guard_batch_size(payload.data)
    resolver = make_resolver(session)
    results: list[dict[str, Any]] = []

    for item in payload.data:
        try:
            clean = validate_payload(module, item, resolver=resolver)
        except FieldError as exc:
            results.append(exc.to_result())
            continue
        clean = _auto_fields(module, clean, session)
        record = create(session, module.api_name, clean, record_id=item.get("id"))
        results.append(
            success_result(record.id, record.created_time, record.modified_time, "record added")
        )

    session.commit()
    return JSONResponse(status_code=_write_status(results, 201), content=write_body(results))


@router.put(
    "/{module}",
    summary="Update records (bulk)",
    description="Each record in `data` must carry its `id`.",
)
def update_records(
    module: ModuleDep,
    session: SessionDep,
    payload: Annotated[RecordsPayload, Body(openapi_examples=UPDATE_EXAMPLES)],
) -> JSONResponse:
    _guard_batch_size(payload.data)
    resolver = make_resolver(session)
    results: list[dict[str, Any]] = []

    for item in payload.data:
        record_id = item.get("id")
        if not record_id:
            results.append(
                error_result("MANDATORY_NOT_FOUND", "required field not found", {"api_name": "id"})
            )
            continue
        record = get(session, module.api_name, str(record_id))
        if record is None:
            results.append(
                error_result("RESOURCE_NOT_FOUND", "the record does not exist", {"id": record_id})
            )
            continue
        try:
            clean = validate_payload(module, item, partial=True, resolver=resolver)
        except FieldError as exc:
            results.append(exc.to_result())
            continue
        record = update(session, record, clean)
        results.append(
            success_result(record.id, record.created_time, record.modified_time, "record updated")
        )

    session.commit()
    return JSONResponse(status_code=_write_status(results, 200), content=write_body(results))


@router.put("/{module}/{record_id}", summary="Update a single record")
def update_record(
    module: ModuleDep,
    record_id: Annotated[str, Path(description="19-digit record ID", example="4876000000200001")],
    session: SessionDep,
    payload: Annotated[RecordsPayload, Body(openapi_examples=UPDATE_EXAMPLES)],
) -> JSONResponse:
    validate_record_id(record_id)
    _guard_batch_size(payload.data)
    record = get(session, module.api_name, record_id)
    if record is None:
        raise ZohoAPIError("RESOURCE_NOT_FOUND", "the record does not exist", {"id": record_id})

    try:
        clean = validate_payload(module, payload.data[0], partial=True, resolver=make_resolver(session))
    except FieldError as exc:
        return JSONResponse(status_code=400, content=write_body([exc.to_result()]))

    record = update(session, record, clean)
    session.commit()
    return JSONResponse(
        status_code=200,
        content=write_body(
            [success_result(record.id, record.created_time, record.modified_time, "record updated")]
        ),
    )


@router.post(
    "/{module}/upsert",
    summary="Upsert records",
    description=(
        "Matches existing records on `duplicate_check_fields` (or `id`). Each result reports "
        "`action: insert | update`."
    ),
)
def upsert_records(
    module: ModuleDep,
    session: SessionDep,
    payload: Annotated[RecordsPayload, Body(openapi_examples=CREATE_EXAMPLES)],
) -> JSONResponse:
    _guard_batch_size(payload.data)
    resolver = make_resolver(session)
    check_fields = payload.duplicate_check_fields or []
    results: list[dict[str, Any]] = []

    for item in payload.data:
        match = None
        if item.get("id"):
            match = get(session, module.api_name, str(item["id"]))
        if match is None and check_fields:
            for candidate in query(session, module.api_name):
                if all(candidate.get(f) == item.get(f) for f in check_fields):
                    match = get(session, module.api_name, candidate["id"])
                    break

        try:
            clean = validate_payload(module, item, partial=match is not None, resolver=resolver)
        except FieldError as exc:
            results.append(exc.to_result())
            continue

        if match is not None:
            record = update(session, match, clean)
            result = success_result(
                record.id, record.created_time, record.modified_time, "record updated"
            )
            result["action"] = "update"
        else:
            clean = _auto_fields(module, clean, session)
            record = create(session, module.api_name, clean)
            result = success_result(
                record.id, record.created_time, record.modified_time, "record added"
            )
            result["action"] = "insert"
        if check_fields:
            result["duplicate_field"] = check_fields[0]
        results.append(result)

    session.commit()
    return JSONResponse(status_code=_write_status(results, 200), content=write_body(results))


@router.delete(
    "/{module}",
    summary="Delete records (bulk)",
    description="Pass `ids` as a comma separated list, max 100.",
)
def delete_records(
    module: ModuleDep,
    session: SessionDep,
    ids: Annotated[str, Query(description="Comma separated record ids", example="4876000000200001,4876000000200002")],
) -> JSONResponse:
    id_list = parse_id_list(ids)
    if not id_list:
        raise ZohoAPIError("REQUIRED_PARAM_MISSING", "required parameter is missing", {"param": "ids"})
    if len(id_list) > settings.max_records_per_write:
        raise ZohoAPIError(
            "LIMIT_EXCEEDED",
            f"maximum number of records allowed is {settings.max_records_per_write}",
            {"given": len(id_list)},
        )

    results = [
        delete_success(record_id)
        if delete(session, module.api_name, record_id)
        else error_result("RESOURCE_NOT_FOUND", "the record does not exist", {"id": record_id})
        for record_id in id_list
    ]
    session.commit()
    return JSONResponse(status_code=_write_status(results, 200), content=write_body(results))


@router.delete("/{module}/{record_id}", summary="Delete a single record")
def delete_record(
    module: ModuleDep,
    record_id: Annotated[str, Path(description="19-digit record ID", example="4876000000200001")],
    session: SessionDep,
) -> JSONResponse:
    validate_record_id(record_id)
    if not delete(session, module.api_name, record_id):
        raise ZohoAPIError("RESOURCE_NOT_FOUND", "the record does not exist", {"id": record_id})
    session.commit()
    return JSONResponse(status_code=200, content=write_body([delete_success(record_id)]))
