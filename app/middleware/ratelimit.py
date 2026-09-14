"""API credit counter that returns Zoho's `API_LIMIT_EXCEEDED` / HTTP 429.

Adds `X-RATELIMIT-*` response headers to every CRM call so the client can be
built against real backoff signals.
"""

import time
from dataclasses import dataclass
from typing import Any

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import settings
from app.middleware.faults import _is_exempt
from app.schemas.zoho import error_body

RATE_LIMITED_PREFIX = "/crm/"


@dataclass
class CreditWindow:
    limit: int
    window_seconds: int
    used: int = 0
    window_started: float = 0.0

    def __post_init__(self) -> None:
        self.window_started = time.time()

    def _roll(self) -> None:
        if time.time() - self.window_started >= self.window_seconds:
            self.window_started = time.time()
            self.used = 0

    @property
    def remaining(self) -> int:
        self._roll()
        return max(0, self.limit - self.used)

    @property
    def reset_at(self) -> int:
        return int(self.window_started + self.window_seconds)

    def consume(self) -> bool:
        self._roll()
        if self.used >= self.limit:
            return False
        self.used += 1
        return True

    def configure(self, limit: int | None = None, remaining: int | None = None) -> None:
        if limit is not None:
            self.limit = limit
        if remaining is not None:
            self.used = max(0, self.limit - remaining)
        self.window_started = time.time()

    def reset(self) -> None:
        self.limit = settings.rate_limit_credits
        self.window_seconds = settings.rate_limit_window_seconds
        self.used = 0
        self.window_started = time.time()

    def snapshot(self) -> dict[str, Any]:
        return {
            "limit": self.limit,
            "used": self.used,
            "remaining": self.remaining,
            "window_seconds": self.window_seconds,
            "reset_at": self.reset_at,
        }


credit_window = CreditWindow(
    limit=settings.rate_limit_credits,
    window_seconds=settings.rate_limit_window_seconds,
)


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path: str = scope.get("path", "")
        if scope["type"] != "http" or _is_exempt(path) or not path.startswith(RATE_LIMITED_PREFIX):
            await self.app(scope, receive, send)
            return

        if not credit_window.consume():
            response = JSONResponse(
                status_code=429,
                content=error_body(
                    "TOO_MANY_REQUESTS",
                    "Many requests fired than the allowed limit for a minute. Please check the header X-RATELIMIT-RESET for the reset time",
                    {"limit": credit_window.limit, "window_seconds": credit_window.window_seconds},
                ),
                headers=self._headers(),
            )
            await response(scope, receive, send)
            return

        async def wrapped_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                for key, value in self._headers().items():
                    headers.append((key.lower().encode(), value.encode()))
            await send(message)

        await self.app(scope, receive, wrapped_send)

    def _headers(self) -> dict[str, str]:
        return {
            "X-RATELIMIT-LIMIT": str(credit_window.limit),
            "X-RATELIMIT-REMAINING": str(credit_window.remaining),
            "X-RATELIMIT-RESET": str(credit_window.reset_at),
        }
