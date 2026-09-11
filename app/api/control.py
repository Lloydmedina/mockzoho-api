"""`/__mock__/*` control plane — reset, seed, fault injection, request log."""

import copy
from typing import Any

from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import SessionDep
from app.auth.tokens import token_store
from app.db import SessionLocal
from app.middleware.faults import fault_state, request_log
from app.middleware.ratelimit import credit_window
from app.modules.registry import MODULES, resolve_module
from app.repository import clear_all, create
from app.utils import now_iso
from seeds.data import SEED_MAP

router = APIRouter(tags=["Mock Control"], prefix="/__mock__")


def load_seeds(session: Session | None = None) -> dict[str, int]:
    """Load all seed fixtures into the database. Used by startup and /reset."""
    own_session = session is None
    session = session or SessionLocal()
    try:
        clear_all(session)
        session.commit()
    except Exception:
        session.rollback()
        if own_session:
            session.close()
        raise

    tally: dict[str, int] = {}
    for module_name, records in SEED_MAP.items():
        count = 0
        for item in records:
            item_copy = copy.deepcopy(item)
            record_id = item_copy.pop("id", None)
            create(session, module_name, item_copy, record_id=record_id)
            count += 1
        tally[module_name] = count
    session.commit()
    if own_session:
        session.close()
    return tally


@router.post("/reset", summary="Reset database to seed state")
def reset_mock() -> JSONResponse:
    tally = load_seeds()
    fault_state.reset()
    credit_window.reset()
    return JSONResponse(
        status_code=200,
        content={"status": "success", "message": "database reset to seeds", "counts": tally},
    )


@router.post("/seed", summary="Load custom fixture data")
def seed_custom(
    session: SessionDep,
    payload: Any = Body(
        ...,
        examples=[
            {
                "summary": "Load two cases",
                "value": {
                    "module": "Cases",
                    "records": [
                        {
                            "id": "4876000000200099",
                            "Subject": "Custom seeded case",
                            "Status": "Open",
                            "Priority": "Medium",
                        }
                    ],
                },
            }
        ],
    ),
) -> JSONResponse:
    module_name = payload.get("module") if isinstance(payload, dict) else None
    records = payload.get("records") if isinstance(payload, dict) else None

    if not module_name or not isinstance(records, list):
        return JSONResponse(
            status_code=400,
            content={"error": "expected {\"module\": \"...\", \"records\": [...]}"},
        )

    module = resolve_module(module_name)
    if module is None:
        return JSONResponse(
            status_code=400,
            content={"error": f"unknown module: {module_name}", "available": list(MODULES)},
        )

    count = 0
    for item in records:
        record_id = item.pop("id", None)
        create(session, module.api_name, item, record_id=record_id)
        count += 1
    session.commit()
    return JSONResponse(status_code=200, content={"status": "success", "module": module.api_name, "loaded": count})


@router.post("/faults", summary="Configure fault injection")
def configure_faults(
    payload: Any = Body(
        ...,
        examples=[
            {
                "summary": "Force 429 on all CRM calls",
                "value": {"error_code": "API_LIMIT_EXCEEDED"},
            },
            {
                "summary": "Inject 500ms latency on Cases endpoints",
                "value": {"latency_ms": 500, "path_contains": "/Cases"},
            },
            {
                "summary": "Fail 30% of requests with INVALID_TOKEN",
                "value": {"error_code": "INVALID_TOKEN", "error_rate": 0.3, "remaining_failures": 10},
            },
        ],
    ),
) -> JSONResponse:
    if not isinstance(payload, dict):
        return JSONResponse(status_code=400, content={"error": "expected a JSON object"})

    if "error_code" in payload:
        fault_state.error_code = payload["error_code"] or None
    if "error_rate" in payload:
        fault_state.error_rate = float(payload["error_rate"])
    if "latency_ms" in payload:
        fault_state.latency_ms = int(payload["latency_ms"])
    if "remaining_failures" in payload:
        fault_state.remaining_failures = payload["remaining_failures"]
    if "path_contains" in payload:
        fault_state.path_contains = payload["path_contains"]

    if payload.get("expire_tokens"):
        token_store.expire_all()

    return JSONResponse(status_code=200, content={"status": "success", "faults": fault_state.snapshot()})


@router.post("/faults/clear", summary="Clear all fault injection")
def clear_faults() -> JSONResponse:
    fault_state.reset()
    return JSONResponse(status_code=200, content={"status": "success", "faults": fault_state.snapshot()})


@router.get("/faults", summary="View current fault configuration")
def view_faults() -> JSONResponse:
    return JSONResponse(status_code=200, content=fault_state.snapshot())


@router.post("/ratelimit", summary="Configure rate limit credits")
def configure_ratelimit(
    payload: Any = Body(
        ...,
        examples=[
            {"summary": "Set remaining credits to 5", "value": {"remaining": 5}},
            {"summary": "Set limit to 10 and reset window", "value": {"limit": 10}},
        ],
    ),
) -> JSONResponse:
    if not isinstance(payload, dict):
        return JSONResponse(status_code=400, content={"error": "expected a JSON object"})
    credit_window.configure(
        limit=payload.get("limit"),
        remaining=payload.get("remaining"),
    )
    return JSONResponse(status_code=200, content={"status": "success", "ratelimit": credit_window.snapshot()})


@router.get("/ratelimit", summary="View rate limit state")
def view_ratelimit() -> JSONResponse:
    return JSONResponse(status_code=200, content=credit_window.snapshot())


@router.post("/ratelimit/reset", summary="Reset rate limit credits to full")
def reset_ratelimit() -> JSONResponse:
    credit_window.reset()
    return JSONResponse(status_code=200, content={"status": "success", "ratelimit": credit_window.snapshot()})


@router.get("/requests", summary="View recent request log")
def view_requests(
    limit: int = Query(default=50, ge=1, le=500),
) -> JSONResponse:
    return JSONResponse(status_code=200, content={"requests": request_log.tail(limit)})


@router.post("/requests/clear", summary="Clear the request log")
def clear_requests() -> JSONResponse:
    request_log.clear()
    return JSONResponse(status_code=200, content={"status": "success"})


@router.get("/health", summary="Health check")
def health() -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "timestamp": now_iso(),
            "tokens_issued": token_store.issued_count,
            "tokens_active": len(token_store.tokens),
        },
    )


@router.get("/modules", summary="List all mock modules and their schemas")
def list_modules() -> JSONResponse:
    from app.modules.registry import module_summary

    return JSONResponse(status_code=200, content={"modules": module_summary()})
