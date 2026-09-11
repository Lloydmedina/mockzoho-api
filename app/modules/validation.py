"""Payload validation and type coercion driven by the module registry."""

from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from app.modules.registry import FieldSpec, ModuleSpec, is_system_field
from app.schemas.zoho import error_result

LookupResolver = Callable[[str, str], dict[str, Any] | None]
"""(module_api_name, record_id) -> record dict or None"""


class FieldError(Exception):
    def __init__(self, code: str, message: str, api_name: str) -> None:
        self.code = code
        self.message = message
        self.api_name = api_name
        super().__init__(message)

    def to_result(self) -> dict[str, Any]:
        return error_result(
            self.code,
            self.message,
            {"api_name": self.api_name, "json_path": f"$.data[0].{self.api_name}"},
        )


def _coerce_bool(value: Any, api_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    raise FieldError("INVALID_DATA", "invalid data", api_name)


def _coerce_number(value: Any, api_name: str, as_int: bool) -> int | float:
    if isinstance(value, bool):
        raise FieldError("INVALID_DATA", "invalid data", api_name)
    try:
        return int(value) if as_int else float(value)
    except (TypeError, ValueError) as exc:
        raise FieldError("INVALID_DATA", "invalid data", api_name) from exc


def _coerce_temporal(value: Any, api_name: str, date_only: bool) -> str:
    if not isinstance(value, str):
        raise FieldError("INVALID_DATA", "invalid data", api_name)
    try:
        if date_only:
            date.fromisoformat(value)
        else:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FieldError("INVALID_DATA", "invalid data", api_name) from exc
    return value


def _coerce_lookup(value: Any, spec: FieldSpec, resolver: LookupResolver | None) -> dict[str, Any]:
    if isinstance(value, str):
        lookup_id, lookup_name = value, None
    elif isinstance(value, dict) and value.get("id"):
        lookup_id, lookup_name = str(value["id"]), value.get("name")
    else:
        raise FieldError("INVALID_DATA", "invalid data", spec.api_name)

    if resolver and spec.lookup_module:
        target = resolver(spec.lookup_module, lookup_id)
        if target is None:
            raise FieldError(
                "INVALID_DATA",
                f"the related record in {spec.lookup_module} does not exist",
                spec.api_name,
            )
        lookup_name = lookup_name or _display_name(target)

    return {"id": lookup_id, "name": lookup_name}


def _display_name(record: dict[str, Any]) -> str | None:
    for key in ("Name", "Subject", "Product_Name", "Case_Number"):
        if record.get(key):
            return str(record[key])
    return None


def coerce_field(value: Any, spec: FieldSpec, resolver: LookupResolver | None = None) -> Any:
    if value is None:
        return None
    match spec.type:
        case "integer":
            return _coerce_number(value, spec.api_name, as_int=True)
        case "double":
            return _coerce_number(value, spec.api_name, as_int=False)
        case "boolean":
            return _coerce_bool(value, spec.api_name)
        case "datetime":
            return _coerce_temporal(value, spec.api_name, date_only=False)
        case "date":
            return _coerce_temporal(value, spec.api_name, date_only=True)
        case "picklist":
            text = str(value)
            if spec.picklist_values and text not in spec.picklist_values:
                raise FieldError(
                    "INVALID_DATA",
                    f"value not in picklist: {', '.join(spec.picklist_values)}",
                    spec.api_name,
                )
            return text
        case "lookup":
            return _coerce_lookup(value, spec, resolver)
        case _:
            return value if isinstance(value, str) else str(value)


def validate_payload(
    module: ModuleSpec,
    payload: dict[str, Any],
    *,
    partial: bool = False,
    resolver: LookupResolver | None = None,
) -> dict[str, Any]:
    """Return the coerced record data, or raise FieldError on the first problem."""
    fields = module.field_map()
    clean: dict[str, Any] = {}

    for key, value in payload.items():
        if key == "id" or is_system_field(key):
            continue
        spec = fields.get(key)
        if spec is None:
            raise FieldError("INVALID_DATA", f"invalid field: {key}", key)
        if spec.read_only:
            continue
        clean[key] = coerce_field(value, spec, resolver)

    if not partial:
        for spec in module.required_fields():
            if clean.get(spec.api_name) in (None, ""):
                raise FieldError("MANDATORY_NOT_FOUND", "required field not found", spec.api_name)

    return clean
