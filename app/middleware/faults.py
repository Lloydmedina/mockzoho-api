"""Fault injection + request logging.

Lets you force `INVALID_TOKEN`, `API_LIMIT_EXCEEDED`, latency, and token expiry
on demand so the client's retry/backoff paths can actually be exercised.
"""

import asyncio
import json
import random
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import settings
from app.schemas.zoho import ERROR_CATALOG, error_body

EXEMPT_PREFIXES = ("/__mock__", "/docs", "/redoc", "/openapi.json", "/health", "/favicon.ico")


@dataclass
class FaultState:
    error_code: str | None = None
    error_rate: float = 1.0
    latency_ms: int = 0
    remaining_failures: int | None = None
    path_contains: str | None = None

    def reset(self) -> None:
        self.error_code = None
        self.error_rate = 1.0
        self.latency_ms = 0
        self.remaining_failures = None
        self.path_contains = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "error_rate": self.error_rate,
            "latency_ms": self.latency_ms,
            "remaining_failures": self.remaining_failures,
            "path_contains": self.path_contains,
        }

    def should_fail(self, path: str) -> bool:
        if not self.error_code:
            return False
        if self.path_contains and self.path_contains not in path:
            return False
        if self.remaining_failures is not None and self.remaining_failures <= 0:
            return False
        if self.error_rate < 1.0 and random.random() > self.error_rate:
            return False
        if self.remaining_failures is not None:
            self.remaining_failures -= 1
        return True


@dataclass
class RequestLog:
    entries: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=settings.request_log_size))

    def add(self, entry: dict[str, Any]) -> None:
        self.entries.append(entry)

    def tail(self, limit: int) -> list[dict[str, Any]]:
        items = list(self.entries)
        return items[-limit:][::-1]

    def clear(self) -> None:
        self.entries.clear()


fault_state = FaultState()
request_log = RequestLog()


def _is_exempt(path: str) -> bool:
    return path.startswith(EXEMPT_PREFIXES)


def _decode_body(raw: bytes) -> Any:
    if not raw:
        return None
    text = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text[:2000]


class FaultInjectionMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        if _is_exempt(path):
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()

        if fault_state.latency_ms:
            await asyncio.sleep(fault_state.latency_ms / 1000)

        body_chunks: list[bytes] = []
        status_holder: dict[str, int] = {}

        async def wrapped_receive() -> Message:
            message = await receive()
            if message["type"] == "http.request":
                body_chunks.append(message.get("body", b""))
            return message

        async def wrapped_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
            await send(message)

        if fault_state.should_fail(path):
            code = fault_state.error_code or "INTERNAL_ERROR"
            status, message = ERROR_CATALOG.get(code, (500, "injected fault"))
            response = JSONResponse(
                status_code=status,
                content=error_body(code, message, {"injected": True}),
            )
            status_holder["status"] = status
            await response(scope, receive, send)
        else:
            await self.app(scope, wrapped_receive, wrapped_send)

        request_log.add(
            {
                "method": scope.get("method"),
                "path": path,
                "query": scope.get("query_string", b"").decode(),
                "status": status_holder.get("status"),
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "authorization": _auth_header(scope),
                "body": _decode_body(b"".join(body_chunks)),
            }
        )


def _auth_header(scope: Scope) -> str | None:
    for key, value in scope.get("headers", []):
        if key == b"authorization":
            text = value.decode()
            return text[:24] + "..." if len(text) > 24 else text
    return None
