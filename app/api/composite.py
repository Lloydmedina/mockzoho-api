"""`POST /crm/v3/__composite_requests` — Zoho Composite API.

Runs up to five sub-requests inside one call. Each sub-request is dispatched
through the ASGI app itself (httpx ASGITransport), so routing, auth, module
validation, fault injection, and rate limiting behave exactly as they do for
direct calls — only the composite envelope, reference resolution, and
rollback semantics live here.

Sub-requests can reuse values from earlier responses via references:
`@{sub_request_id:$.json.path}` anywhere inside `uri`, `params`, or `body`.
"""

import re
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import delete as sa_delete
from sqlalchemy import select

from app.auth.dependency import require_token
from app.db import SessionLocal
from app.models import Record
from app.schemas.zoho import ZohoAPIError, error_body

router = APIRouter(tags=["Composite"], dependencies=[Depends(require_token)])

MAX_SUB_REQUESTS = 5
COMPOSITE_VERSION = 3
ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
FORBIDDEN_HEADERS = {"authorization", "x-crm-org"}
COMPOSITE_ENDPOINT = "__composite_requests"
ROLLBACK_MESSAGE = (
    "the transaction was rolled back since another sub request "
    "in the same transaction failed."
)

SUB_REQUEST_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_]*$")
URI_RE = re.compile(r"^/crm(?:/.*)?/v(\d+(?:\.\d+)?)/.+$")
REF_RE = re.compile(r"@\{([A-Za-z0-9][A-Za-z0-9_]*):([^}]+)\}")
JSONPATH_TOKEN_RE = re.compile(
    r"\.([A-Za-z0-9_]+)|\[\s*(-?\d+)\s*\]|\[\s*'([^']*)'\s*\]|\[\s*\"([^\"]*)\"\s*\]"
)


class _InvalidReference(Exception):
    """A @{id:path} reference could not be resolved."""


def _executed_result(status_code: int, headers: dict[str, str], body: Any) -> dict[str, Any]:
    return {
        "code": "SUCCESS",
        "details": {
            "response": {
                "headers": headers,
                "status_code": status_code,
                "body": body,
            }
        },
        "message": "composite sub request executed successfully",
        "status": "success",
    }


def _rollback_marker(code: str, failed_index: int) -> dict[str, Any]:
    return {
        "code": code,
        "details": {"rollbacked_by_sub_request_index": failed_index},
        "message": ROLLBACK_MESSAGE,
        "status": "error",
    }


# ---------------------------------------------------------------------------
# Sub-request validation
# ---------------------------------------------------------------------------


def _validate_subrequest(sub: Any, seen_ids: set[str]) -> dict[str, Any] | None:
    """Return a Zoho error body if the sub-request is invalid, else None."""
    if not isinstance(sub, dict):
        return error_body("INVALID_DATA", "each sub-request must be a JSON object")

    uri, method = sub.get("uri"), sub.get("method")
    if not isinstance(uri, str) or not uri:
        return error_body("MANDATORY_NOT_FOUND", "mandatory key uri is missing or invalid")
    if not isinstance(method, str) or not method:
        return error_body("MANDATORY_NOT_FOUND", "mandatory key method is missing or invalid")

    match = URI_RE.match(uri)
    if not match:
        return error_body(
            "MANDATORY_NOT_FOUND",
            "uri must match the pattern /crm/v{version}/<api>",
            {"uri": uri},
        )
    if method.upper() not in ALLOWED_METHODS:
        return error_body(
            "INVALID_DATA",
            f"invalid method: {method}",
            {"allowed": sorted(ALLOWED_METHODS)},
        )

    sub_id = sub.get("sub_request_id")
    if sub_id is not None:
        if not isinstance(sub_id, str) or not SUB_REQUEST_ID_RE.match(sub_id):
            return error_body(
                "INVALID_DATA",
                f"invalid sub_request_id: {sub_id}",
                {"pattern": "[a-zA-Z0-9][a-zA-Z0-9_]*"},
            )
        if sub_id in seen_ids:
            return error_body("DUPLICATE_DATA", f"duplicate sub_request_id: {sub_id}")
        seen_ids.add(sub_id)

    params = sub.get("params")
    if params is not None and not isinstance(params, dict):
        return error_body("INVALID_DATA", "params must be a JSON object")

    headers = sub.get("headers")
    if headers is not None:
        if not isinstance(headers, dict):
            return error_body("INVALID_DATA", "headers must be a JSON object")
        bad = FORBIDDEN_HEADERS & {str(k).lower() for k in headers}
        if bad:
            return error_body(
                "INVALID_DATA",
                f"headers not allowed in sub-requests: {', '.join(sorted(bad))}",
            )

    if float(match.group(1)) > COMPOSITE_VERSION:
        return error_body(
            "NOT_ALLOWED",
            f"sub-request api version v{match.group(1)} is higher than the composite version v{COMPOSITE_VERSION}",
        )
    if uri.rstrip("/").endswith(COMPOSITE_ENDPOINT):
        return error_body(
            "NOT_SUPPORTED",
            "the composite API cannot be invoked inside a composite request",
        )
    return None


# ---------------------------------------------------------------------------
# References: @{sub_request_id:$.json.path}
# ---------------------------------------------------------------------------


def _ref_ids_in(node: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(node, str):
        found.update(m.group(1) for m in REF_RE.finditer(node))
    elif isinstance(node, list):
        for item in node:
            found.update(_ref_ids_in(item))
    elif isinstance(node, dict):
        for key, value in node.items():
            found.update(_ref_ids_in(key))
            found.update(_ref_ids_in(value))
    return found


def _sub_ref_ids(sub: dict[str, Any]) -> set[str]:
    return _ref_ids_in(sub.get("uri")) | _ref_ids_in(sub.get("params")) | _ref_ids_in(
        sub.get("body")
    )


def _resolve_jsonpath(data: Any, path: str) -> Any:
    """Evaluate a small JSONPath subset: `$.key`, `.key`, `[n]`, `["key"]`, `['key']`."""
    path = path.strip()
    if not path.startswith("$"):
        raise _InvalidReference(f"invalid reference path: {path}")
    current, pos = data, 1
    while pos < len(path):
        match = JSONPATH_TOKEN_RE.match(path, pos)
        if not match:
            raise _InvalidReference(f"invalid reference path: {path}")
        key, index = match.group(1) or match.group(3) or match.group(4), match.group(2)
        if key is not None:
            if not isinstance(current, dict) or key not in current:
                raise _InvalidReference(f"reference path has no value: {path}")
            current = current[key]
        else:
            if not isinstance(current, list):
                raise _InvalidReference(f"reference path has no value: {path}")
            i = int(index)
            if i >= len(current) or i < -len(current):
                raise _InvalidReference(f"reference path has no value: {path}")
            current = current[i]
        pos = match.end()
    return current


def _lookup_reference(ref_id: str, path: str, responses: dict[str, Any]) -> Any:
    if ref_id not in responses:
        raise _InvalidReference(f"reference @{ref_id}:{path} points to a sub-request that was not executed")
    return _resolve_jsonpath(responses[ref_id], path)


def _substitute(node: Any, responses: dict[str, Any]) -> Any:
    """Replace @{id:path} references using completed sub-request bodies."""
    if isinstance(node, str):
        whole = REF_RE.fullmatch(node)
        if whole:
            return _lookup_reference(whole.group(1), whole.group(2), responses)
        return REF_RE.sub(
            lambda m: str(_lookup_reference(m.group(1), m.group(2), responses)), node
        )
    if isinstance(node, list):
        return [_substitute(item, responses) for item in node]
    if isinstance(node, dict):
        return {
            _substitute(key, responses): _substitute(value, responses)
            for key, value in node.items()
        }
    return node


def _execution_order(
    subs: list[Any], runnable: list[int], parallel: bool
) -> tuple[list[int], set[int]]:
    """Return (execution order, looped indices). Parallel mode topologically
    orders sub-requests by their references; unresolvable cycles report
    LOOPING_FOUND. Sequential mode keeps input order."""
    if not parallel:
        return list(runnable), set()

    id_to_index = {
        subs[i]["sub_request_id"]: i for i in runnable if subs[i].get("sub_request_id")
    }
    pending = {
        i: {id_to_index[r] for r in _sub_ref_ids(subs[i]) if r in id_to_index}
        for i in runnable
    }
    order, done = [], set()
    while pending:
        progressed = False
        for i in runnable:
            if i in pending and pending[i] <= done:
                order.append(i)
                done.add(i)
                del pending[i]
                progressed = True
        if not progressed:
            break
    return order, set(pending)


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


def _snapshot_records() -> list[dict[str, Any]]:
    with SessionLocal() as session:
        return [
            {
                "id": r.id,
                "module": r.module,
                "data": dict(r.data),
                "created_time": r.created_time,
                "modified_time": r.modified_time,
            }
            for r in session.scalars(select(Record))
        ]


def _restore_records(snapshot: list[dict[str, Any]]) -> None:
    with SessionLocal() as session:
        session.execute(sa_delete(Record))
        for row in snapshot:
            session.add(Record(**row))
        session.commit()


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


async def _dispatch(
    client: httpx.AsyncClient,
    authorization: str,
    method: str,
    uri: str,
    params: dict[str, Any],
    body: Any,
    extra_headers: Any,
) -> tuple[int, dict[str, str], Any]:
    headers = {"Authorization": authorization}
    if isinstance(extra_headers, dict):
        headers.update({str(k): str(v) for k, v in extra_headers.items()})

    response = await client.request(
        method.upper(), uri, params=params or None, json=body, headers=headers
    )
    try:
        parsed = response.json()
    except ValueError:
        parsed = response.text or None
    return response.status_code, dict(response.headers), parsed


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/__composite_requests",
    summary="Composite API — batch up to 5 sub-requests",
    description=(
        "Executes up to 5 sub-requests in one call and returns a per-sub-request "
        "envelope `{\"code\", \"details\": {\"response\": {...}}, \"message\", \"status\"}`.\n\n"
        "- Sub-requests may carry an optional `sub_request_id` and reference earlier "
        "responses with `@{id:$.json.path}` inside `uri`, `params`, or `body`.\n"
        "- `rollback_on_fail` (default false): on the first failed sub-request, all "
        "writes made by the composite call are reverted; executed sub-requests are "
        "marked `ROLLBACK_PERFORMED` and unexecuted ones `PROCESSING_STOPPED`.\n"
        "- `parallel_execution` (default true, default false when `rollback_on_fail`): "
        "independent sub-requests are reordered by reference dependencies; mutual "
        "references fail with `LOOPING_FOUND`. It cannot be true together with "
        "`rollback_on_fail` (`AMBIGUITY_DURING_PROCESSING`).\n\n"
        "Top-level status: `rollback_on_fail` → 200 or 400 when rolled back; "
        "otherwise 200 when all sub-requests were triggered, 207 when some were, "
        "400 when none were. Sub-requests consume rate-limit credits like direct "
        "calls (real Zoho charges 1-2 credits per composite — mock simplification)."
    ),
)
async def composite_requests(
    request: Request,
    payload: Annotated[Any, Body(...)],
) -> JSONResponse:
    if not isinstance(payload, dict) or payload.get("__composite_requests") is None:
        raise ZohoAPIError(
            "MANDATORY_NOT_FOUND",
            "the mandatory key __composite_requests is missing",
            {"key": "__composite_requests"},
        )

    subs = payload["__composite_requests"]
    if not isinstance(subs, list) or not subs:
        raise ZohoAPIError(
            "INVALID_DATA", "__composite_requests must be a non-empty JSON array"
        )
    for key in ("rollback_on_fail", "parallel_execution"):
        if key in payload and not isinstance(payload[key], bool):
            raise ZohoAPIError("INVALID_DATA", f"{key} must be true or false")
    rollback_on_fail = payload["rollback_on_fail"] if "rollback_on_fail" in payload else False
    parallel = (
        payload["parallel_execution"]
        if "parallel_execution" in payload
        else not rollback_on_fail
    )
    if rollback_on_fail and parallel:
        raise ZohoAPIError(
            "AMBIGUITY_DURING_PROCESSING",
            "rollback_on_fail and parallel_execution keys cannot be true in the same request",
        )
    if len(subs) > MAX_SUB_REQUESTS:
        raise ZohoAPIError(
            "INVALID_DATA",
            f"maximum {MAX_SUB_REQUESTS} sub-requests allowed in a composite request",
            {"given": len(subs)},
        )

    results: list[dict[str, Any] | None] = [None] * len(subs)
    seen_ids: set[str] = set()
    runnable: list[int] = []
    for i, sub in enumerate(subs):
        error = _validate_subrequest(sub, seen_ids)
        if error is None and sub.get("sub_request_id") in _sub_ref_ids(sub):
            error = error_body(
                "INVALID_REFERENCE", "a sub-request cannot reference itself"
            )
        if error is None:
            runnable.append(i)
        else:
            results[i] = error

    if rollback_on_fail:
        # Sequential by definition; walk every index so invalid sub-requests
        # also trigger the rollback at their position.
        order, looped = list(range(len(subs))), set()
    else:
        order, looped = _execution_order(subs, runnable, parallel)
        for i in looped:
            results[i] = error_body(
                "LOOPING_FOUND", "the sub-requests are referring to each other"
            )

    snapshot = _snapshot_records() if rollback_on_fail else None
    responses: dict[str, Any] = {}
    fail_index: int | None = None
    triggered = 0
    authorization = request.headers.get("authorization", "")

    transport = httpx.ASGITransport(app=request.app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://mock.local"
    ) as client:
        for i in order:
            if results[i] is not None:
                # Pre-validation error under rollback_on_fail aborts the batch.
                if rollback_on_fail:
                    fail_index = i
                    break
                continue

            sub = subs[i]
            try:
                uri = _substitute(sub["uri"], responses)
                params = _substitute(sub.get("params") or {}, responses)
                body = (
                    _substitute(sub["body"], responses) if "body" in sub else None
                )
            except _InvalidReference as exc:
                results[i] = error_body("INVALID_REFERENCE", str(exc))
                if rollback_on_fail:
                    fail_index = i
                    break
                continue

            status_code, headers, parsed = await _dispatch(
                client,
                authorization,
                sub["method"],
                uri,
                params,
                body,
                sub.get("headers"),
            )
            triggered += 1
            results[i] = _executed_result(status_code, headers, parsed)
            if sub.get("sub_request_id"):
                responses[sub["sub_request_id"]] = parsed
            if rollback_on_fail and status_code >= 400:
                fail_index = i
                break

    if fail_index is not None:
        _restore_records(snapshot or [])
        for j, result in enumerate(results):
            if j == fail_index:
                continue
            if result is None:
                results[j] = _rollback_marker("PROCESSING_STOPPED", fail_index)
            elif result.get("code") == "SUCCESS" and "response" in result.get(
                "details", {}
            ):
                results[j] = _rollback_marker("ROLLBACK_PERFORMED", fail_index)

    for i, result in enumerate(results):
        if result is None:
            results[i] = error_body("INTERNAL_ERROR", "sub-request was not executed")

    if rollback_on_fail:
        status = 400 if fail_index is not None else 200
    else:
        status = 200 if triggered == len(subs) else (207 if triggered else 400)
    return JSONResponse(status_code=status, content={"__composite_requests": results})
