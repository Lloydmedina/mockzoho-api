"""/crm/v3/functions/{api_name}/actions/execute - simulates Zoho standalone
(REST API) functions. Pricing rules live here server-side, mirroring the Deluge
function that owns them in the real CRM: only the total comes back."""

import json
from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy.orm import Session

from app.api.deps import SessionDep
from app.auth.dependency import require_token
from app.repository import query
from app.schemas.zoho import ZohoAPIError
from app.utils import new_record_id

router = APIRouter(tags=["Functions"])

PRICING_FUNCTION_NAME = "calculate_visit_total"

# Pricing rates owned by the "Zoho side" - never returned to callers.
TECH_RATE = 45.0
HELPER_RATE = 30.0
TRAVEL_RATE_PER_KM = 0.50
DEFAULT_GAS_RATE = 25.0

# Query params consumed by the API itself - everything else is a function argument.
_META_PARAMS = {"auth_type", "zapikey"}


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _gas_rate(session: Session, gas_type: str) -> float:
    """Resolve the per-kg rate from the Gas_Types module; DEFAULT_GAS_RATE fallback."""
    if not gas_type:
        return DEFAULT_GAS_RATE
    for record in query(session, "Gas_Types"):
        code = str(record.get("Code") or "").upper()
        name = str(record.get("Name") or "").upper()
        if gas_type.upper() in (code, name):
            return _num(record.get("Rate_Per_Kg")) or DEFAULT_GAS_RATE
    return DEFAULT_GAS_RATE


def _check_auth(request: Request) -> None:
    """Zoho functions accept OAuth (`Zoho-oauthtoken` header) or `zapikey` param."""
    auth_type = request.query_params.get("auth_type", "oauth")
    if auth_type == "apikey":
        if not request.query_params.get("zapikey"):
            raise ZohoAPIError("INVALID_TOKEN", "zapikey is missing")
        return
    require_token(request.headers.get("authorization"))


async def _read_arguments(request: Request) -> dict[str, Any]:
    args: dict[str, Any] = {}
    for k, v in request.query_params.items():
        if k in _META_PARAMS:
            continue
        if k == "arguments":
            try:
                decoded = json.loads(v)
                if isinstance(decoded, dict):
                    args.update(decoded)
                    continue
            except (json.JSONDecodeError, ValueError):
                pass
        args[k] = v
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        if isinstance(body, dict):
            inner = body.get("arguments")
            if isinstance(inner, str):
                try:
                    inner = json.loads(inner)
                except (json.JSONDecodeError, ValueError):
                    raise ZohoAPIError(
                        "INVALID_DATA",
                        "arguments must be a JSON-encoded map",
                    )
            args.update(inner if isinstance(inner, dict) else body)
    elif request.method in {"POST", "PUT", "PATCH"}:
        form = await request.form()
        inner = form.get("arguments")
        if isinstance(inner, str):
            try:
                decoded = json.loads(inner)
            except (json.JSONDecodeError, ValueError):
                raise ZohoAPIError(
                    "INVALID_DATA",
                    "arguments must be a JSON-encoded map",
                )
            args.update(decoded)
        else:
            args.update(dict(form))
    return args

@router.get("/functions/{api_name}/actions/execute")
@router.post("/functions/{api_name}/actions/execute")
async def execute_function(api_name: str, request: Request, session: SessionDep):
    _check_auth(request)
    if api_name != PRICING_FUNCTION_NAME:
        raise ZohoAPIError(
            "INVALID_URL_PATTERN",
            f"No function named '{api_name}' is exposed as a REST API",
        )

    args = await _read_arguments(request)

    gas_rate = _gas_rate(session, str(args.get("gas_type") or ""))

    technician_cost = round(_num(args.get("technician_hours")) * TECH_RATE, 2)
    helper_cost = round(_num(args.get("helper_hours")) * HELPER_RATE, 2)
    travel_cost = round(_num(args.get("kilometers_traveled")) * TRAVEL_RATE_PER_KM, 2)
    gas_cost = round(_num(args.get("gas_quantity_kg")) * gas_rate, 2)
    meal_expense = round(_num(args.get("meal_expense")), 2)
    other_expenses = round(_num(args.get("other_expenses")), 2)
    total = round(
        technician_cost + helper_cost + travel_cost + gas_cost + meal_expense + other_expenses,
        2,
    )

    # Real Zoho envelope: the Deluge return value lands in details.output as a
    # string. A function returning a map serializes it as JSON, so callers get
    # the full cost breakdown alongside the total.
    output = {
        "technician_cost": technician_cost,
        "helper_cost": helper_cost,
        "travel_cost": travel_cost,
        "gas_cost": gas_cost,
        "meal_expense": meal_expense,
        "other_expenses": other_expenses,
        "total_amount": total,
        "currency": "EUR",
    }
    return {
        "code": "success",
        "details": {
            "output": json.dumps(output),
            "output_type": "string",
            "id": new_record_id(),
        },
        "message": "function executed successfully",
    }
