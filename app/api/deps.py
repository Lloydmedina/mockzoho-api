from typing import Annotated

from fastapi import Depends, Header, Path, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.modules.registry import MODULE_NAMES, ModuleSpec, resolve_module
from app.schemas.zoho import ZohoAPIError

MODULE_DOC = f"Zoho module API name. Available in this mock: {', '.join(MODULE_NAMES)}"


def module_spec(
    module: Annotated[str, Path(description=MODULE_DOC, examples=["Cases"])],
) -> ModuleSpec:
    spec = resolve_module(module)
    if spec is None:
        raise ZohoAPIError(
            "INVALID_MODULE",
            "the module name given seems to be invalid",
            {"module": module, "available_modules": list(MODULE_NAMES)},
        )
    return spec


def pagination(
    page: Annotated[int, Query(ge=1, description="1-based page number")] = 1,
    per_page: Annotated[int, Query(ge=1, description="Records per page (max 200)")] = None,  # type: ignore[assignment]
) -> tuple[int, int]:
    resolved = settings.default_per_page if per_page is None else per_page
    if resolved > settings.max_per_page:
        raise ZohoAPIError(
            "INVALID_QUERY_PARAM",
            f"per_page cannot exceed {settings.max_per_page}",
            {"parameter": "per_page", "given": resolved},
        )
    return page, resolved


def field_list(
    fields: Annotated[
        str | None,
        Query(description="Comma separated field API names to project", examples=["Subject,Status,Priority"]),
    ] = None,
) -> list[str] | None:
    if not fields:
        return None
    parsed = [part.strip() for part in fields.split(",") if part.strip()]
    return parsed or None


def required_field_list(
    fields: Annotated[
        str | None,
        Query(description="Comma separated field API names (mandatory when listing records)", examples=["Subject,Status,Priority"]),
    ] = None,
) -> list[str]:
    if not fields or not fields.strip():
        raise ZohoAPIError(
            "REQUIRED_PARAM_MISSING",
            "required parameter is missing",
            {"param": "fields"},
        )
    parsed = [part.strip() for part in fields.split(",") if part.strip()]
    if not parsed:
        raise ZohoAPIError(
            "REQUIRED_PARAM_MISSING",
            "required parameter is missing",
            {"param": "fields"},
        )
    return parsed


def modified_since(
    if_modified_since: Annotated[
        str | None,
        Header(alias="If-Modified-Since", description="ISO 8601 timestamp; returns only newer records"),
    ] = None,
) -> str | None:
    return if_modified_since


SessionDep = Annotated[Session, Depends(get_session)]
ModuleDep = Annotated[ModuleSpec, Depends(module_spec)]
PaginationDep = Annotated[tuple[int, int], Depends(pagination)]
FieldsDep = Annotated[list[str] | None, Depends(field_list)]
RequiredFieldsDep = Annotated[list[str], Depends(required_field_list)]
ModifiedSinceDep = Annotated[str | None, Depends(modified_since)]


def parse_id_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]
