"""/crm/v3/functions/{api_name}/actions/execute - simulates Zoho standalone
(REST API) functions. Pricing rules live here server-side, mirroring the Deluge
function that owns them in the real CRM: only the total comes back."""

import json
from typing import Any

from fastapi import APIRouter, Request

from app.auth.dependency import require_token
from app.schemas.zoho import ZohoAPIError
from app.utils import new_record_id

router = APIRouter(tags=["Functions"])

PRICING_FUNCTION_NAME = "calculate_visit_total"

# Pricing rates owned by the "Zoho side" - never returned to callers.
TECH_RATE = 45.0
HELPER_RATE = 30.0
TRAVEL_RATE_PER_KM = 0.50
DEFAULT_GAS_RATE = 25.0
GAS_RATES_PER_KG = {
    "R32": 25.0,
    "R410A": 30.0,
    "R134A": 22.0,
}

# Query params consumed by the API itself - everything else is a function argument.
_META_PARAMS = {"auth_type", "zapikey"}


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _check_auth(request: Request) -> None:
    """Zoho functions accept OAuth (`Zoho-oauthtoken` header) or `zapikey` param."""
    auth_type = request.query_params.get("auth_type", "oauth")
    if auth_type == "apikey":
        if not request.query_params.get("zapikey"):
            raise ZohoAPIError("INVALID_TOKEN", "zapikey is missing")
        return
    require_token(request.headers.get("authorization"))


async def _read_arguments(request: Request) -> dict[str, Any]:
    """Zoho functions accept args as query params, a form/JSON `arguments` key, or a raw JSON body."""
    args: dict[str, Any] = {
        k: v for k, v in request.query_params.items() if k not in _META_PARAMS
    }
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        if isinstance(body, dict):
            inner = body.get("arguments")
            if isinstance(inner, str):
                inner = json.loads(inner)
            args.update(inner if isinstance(inner, dict) else body)
    else:
        form = await request.form()
        inner = form.get("arguments")
        if isinstance(inner, str):
            args.update(json.loads(inner))
        else:
            args.update(dict(form))
    return args


@router.post("/functions/{api_name}/actions/execute")
async def execute_function(api_name: str, request: Request):
    _check_auth(request)
    if api_name != PRICING_FUNCTION_NAME:
        raise ZohoAPIError(
            "INVALID_URL_PATTERN",
            f"No function named '{api_name}' is exposed as a REST API",
        )

    args = await _read_arguments(request)

    gas_type = str(args.get("gas_type") or "").upper()
    gas_rate = GAS_RATES_PER_KG.get(gas_type, DEFAULT_GAS_RATE)

    total = round(
        _num(args.get("technician_hours")) * TECH_RATE
        + _num(args.get("helper_hours")) * HELPER_RATE
        + _num(args.get("kilometers_traveled")) * TRAVEL_RATE_PER_KM
        + _num(args.get("gas_quantity_kg")) * gas_rate
        + _num(args.get("meal_expense"))
        + _num(args.get("other_expenses")),
        2,
    )

    # Real Zoho envelope: the Deluge return value lands in details.output as a
    # string, alongside output_type and a function-execution record id.
    return {
        "code": "success",
        "details": {
            "output": f"{total:.2f}",
            "output_type": "string",
            "id": new_record_id(),
        },
        "message": "function executed successfully",
    }
