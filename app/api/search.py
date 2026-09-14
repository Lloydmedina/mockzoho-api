"""`GET /crm/v3/{module}/search` — criteria, email, phone and word search."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse

from app.api.deps import FieldsDep, ModuleDep, PaginationDep, SessionDep
from app.api.filters import Predicate, parse_criteria
from app.auth.dependency import require_token
from app.modules.registry import ModuleSpec
from app.repository import paginate, project, query
from app.schemas.zoho import ZohoAPIError, record_list_body

router = APIRouter(tags=["Search"], dependencies=[Depends(require_token)])

EMAIL_FIELDS = ("Email", "Secondary_Email")
PHONE_FIELDS = ("Phone", "Mobile", "Technician_Phone")


def _word_predicate(module: ModuleSpec, word: str) -> Predicate:
    needle = word.lower()
    searchable = [f.api_name for f in module.fields if f.type in {"string", "text", "email", "phone", "picklist"}]

    def predicate(payload: dict) -> bool:
        for field in searchable:
            value = payload.get(field)
            if isinstance(value, dict):
                value = value.get("name")
            if value and needle in str(value).lower():
                return True
        return False

    return predicate


def _any_field_predicate(fields: tuple[str, ...], needle: str) -> Predicate:
    lowered = needle.lower()

    def predicate(payload: dict) -> bool:
        return any(str(payload.get(field, "")).lower() == lowered for field in fields)

    return predicate


@router.get(
    "/{module}/search",
    summary="Search records",
    description=(
        "Exactly one of `criteria`, `email`, `phone` or `word` is required.\n\n"
        "Criteria syntax matches Zoho: `(Status:equals:Open)` or "
        "`((Status:equals:Open)and(Priority:equals:High))`. Supported operators: "
        "`equals`, `not_equal`, `starts_with`, `ends_with`, `contains`, `in`, "
        "`greater_than`, `greater_equal`, `less_than`, `less_equal`.\n\n"
        "**Returns HTTP 204 when nothing matches.**"
    ),
)
def search_records(
    module: ModuleDep,
    session: SessionDep,
    pagination: PaginationDep,
    fields: FieldsDep,
    criteria: Annotated[
        str | None,
        Query(description="Zoho criteria expression", examples=["(Status:equals:Open)"]),
    ] = None,
    email: Annotated[str | None, Query(description="Exact email match")] = None,
    phone: Annotated[str | None, Query(description="Exact phone match")] = None,
    word: Annotated[str | None, Query(description="Free text match across text fields")] = None,
) -> Response:
    provided = [value for value in (criteria, email, phone, word) if value]
    if not provided:
        raise ZohoAPIError(
            "REQUIRED_PARAM_MISSING",
            "one of criteria, email, phone or word is required",
            {"params": ["criteria", "email", "phone", "word"]},
        )
    if len(provided) > 1:
        raise ZohoAPIError(
            "INVALID_QUERY_PARAM",
            "only one search parameter is allowed per request",
            {"given": len(provided)},
        )

    if criteria:
        predicate = parse_criteria(criteria)
    elif email:
        predicate = _any_field_predicate(EMAIL_FIELDS, email)
    elif phone:
        predicate = _any_field_predicate(PHONE_FIELDS, phone)
    else:
        predicate = _word_predicate(module, word or "")

    page, per_page = pagination
    payloads = query(session, module.api_name, predicate=predicate)
    window, more_records = paginate(payloads, page, per_page)

    if not window:
        return Response(status_code=204)

    return JSONResponse(
        status_code=200,
        content=record_list_body(project(window, fields), page, per_page, more_records),
    )
