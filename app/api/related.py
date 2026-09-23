"""`GET /crm/v3/{module}/{id}/{related_list}` — related record traversal."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response
from fastapi.responses import JSONResponse

from app.api.deps import FieldsDep, ModuleDep, PaginationDep, SessionDep, validate_record_id
from app.auth.dependency import require_token
from app.repository import get, paginate, project, query
from app.schemas.zoho import ZohoAPIError, record_list_body

router = APIRouter(tags=["Records"], dependencies=[Depends(require_token)])


@router.get(
    "/{module}/{record_id}/{related_list}",
    summary="Get related records",
    description=(
        "Returns records from a related module linked to the parent record via a lookup field. "
        "Available related lists are documented on each module in the registry.\n\n"
        "**Returns HTTP 204 when the parent or no related records are found.**"
    ),
)
def get_related_records(
    module: ModuleDep,
    record_id: Annotated[str, Path(description="19-digit record ID", example="4876000000200001")],
    related_list: Annotated[str, Path(description="Related list name (e.g. Visits, Labor_Costs, Spare_Parts, Case_Actions)", example="Visits")],
    session: SessionDep,
    pagination: PaginationDep,
    fields: FieldsDep,
) -> Response:
    validate_record_id(record_id)
    parent = get(session, module.api_name, record_id)
    if parent is None:
        return Response(status_code=204)

    related_spec = module.related_lists.get(related_list)
    if related_spec is None:
        raise ZohoAPIError(
            "INVALID_URL_PATTERN",
            "the related list name given seems to be invalid",
            {
                "module": module.api_name,
                "related_list": related_list,
                "available": list(module.related_lists),
            },
        )

    target_module, lookup_field = related_spec
    page, per_page = pagination

    payloads = query(
        session,
        target_module,
        predicate=lambda p: _matches_parent(p, lookup_field, record_id),
    )

    window, more_records = paginate(payloads, page, per_page)
    if not window:
        return Response(status_code=204)

    return JSONResponse(
        status_code=200,
        content=record_list_body(project(window, fields), page, per_page, more_records),
    )


def _matches_parent(payload: dict, lookup_field: str, parent_id: str) -> bool:
    value = payload.get(lookup_field)
    if isinstance(value, dict):
        return str(value.get("id", "")) == str(parent_id)
    return str(value or "") == str(parent_id)
