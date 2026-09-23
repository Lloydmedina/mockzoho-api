"""Mock Zoho CRM API — FastAPI application factory."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from app.api.coql import router as coql_router
from app.api.control import load_seeds, router as control_router
from app.api.records import router as records_router
from app.api.related import router as related_router
from app.api.search import router as search_router
from app.auth.routes import router as oauth_router
from app.config import settings
from app.db import create_schema, drop_schema
from app.docs import get_docs_html
from app.middleware.faults import FaultInjectionMiddleware
from app.middleware.ratelimit import RateLimitMiddleware
from app.schemas.zoho import ZohoAPIError, error_body

DESCRIPTION = """
## Mock Zoho CRM API

A high-fidelity mock of the **Zoho CRM v3 REST API** for local development and testing.

### Getting started

1. **Get a token** — click **Try it out** on `POST /oauth/v2/token` below and fill in
   `client_id=1000.MOCKCLIENTID`, `client_secret=mock_client_secret`,
   `refresh_token=1000.mockrefreshtoken.refresh` (any values work unless
   `MOCKZOHO_EXPECTED_*` env vars are set).

2. **Authorize** — click the **Authorize** button above and paste
   `Zoho-oauthtoken <your_access_token>`.

3. **Try it out** — explore the endpoints below. Start with `GET /crm/v3/Cases`.

4. **Learn the OAuth flow** — click the red **OAuth Presentation** button
   in the top-right corner to open an interactive slide deck on Zoho
   OAuth 2.0 and token lifecycle.

### Available modules

`Cases`, `Visits`, `Products`, `Labor_Costs`, `Spare_Parts`, `Case_Actions`

### Mock control plane

- `POST /__mock__/reset` — reset database to seed state
- `POST /__mock__/faults` — inject errors, latency, or token expiry
- `POST /__mock__/ratelimit` — configure rate limit credits
- `GET /__mock__/requests` — view recent request log
- `GET /__mock__/modules` — view module schemas

### Pointing your app here

Set these env vars in `tadiran-force-app-api`:

```
ZOHO_BASE_URL=http://localhost:8090/crm/v3
ZOHO_ACCOUNTS_URL=http://localhost:8090
```

### Error codes

All errors use the Zoho envelope: `{"code": "...", "details": {...}, "message": "...", "status": "error"}`.

| Code | HTTP | Trigger |
|------|------|---------|
| `INVALID_TOKEN` | 401 | Missing/bad `Authorization` header or expired token |
| `OAUTH_SCOPE_MISMATCH` | 401 | Token lacks required scope |
| `AUTHENTICATION_FAILURE` | 401 | Authentication failed |
| `NO_PERMISSION` | 403 | User lacks permission for the resource |
| `FEATURE_NOT_SUPPORTED` | 403 | Feature not enabled for the edition (injectable via `/__mock__/faults`) |
| `INVALID_MODULE` | 400 | Unknown module name in the URL |
| `MANDATORY_NOT_FOUND` | 400 | Missing required field on write |
| `INVALID_DATA` | 400 | Bad field value or data type |
| `INVALID_QUERY_PARAM` | 400 | Bad query parameter |
| `INVALID_QUERY` | 400 | Malformed COQL query |
| `REQUIRED_PARAM_MISSING` | 400 | Required parameter missing |
| `DUPLICATE_DATA` | 400 | Duplicate value on a unique field |
| `LIMIT_EXCEEDED` | 400 | Bulk write exceeds 100 records or COQL exceeds 50 fields |
| `PATTERN_NOT_MATCHED` | 400 | Parameter value not in allowed set (e.g. `sort_order`) |
| `INVALID_REQUEST_METHOD` | 400 | Wrong HTTP method for a `/crm/` endpoint |
| `LICENSE_LIMIT_EXCEEDED` | 400 | License limit exceeded (injectable via `/__mock__/faults`) |
| `UNABLE_TO_PARSE_DATA_TYPE` | 400 | Non-numeric record ID where integer expected |
| `RESOURCE_NOT_FOUND` | 404 | Single-record GET on a non-existent ID |
| `INVALID_URL_PATTERN` | 404 | Bad URL or unknown related list name |
| `API_LIMIT_EXCEEDED` | 429 | API credit exhaustion (injectable via `/__mock__/faults`) |
| `TOO_MANY_REQUESTS` | 429 | Rate limit hit — credits exhausted for the window |
| `INTERNAL_ERROR` | 500 | Internal server error (injectable via `/__mock__/faults`) |
| `RECORD_LOCKED` | 400 | Record locked by another process (injectable) |
| `NOT_APPROVED` | 400 | Record not approved (injectable) |
| `MULTIPLE_OR_MULTI_ERRORS` | 400 | Multiple errors in one request (injectable) |
| `FILE_TOO_LARGE` | 413 | File upload exceeds limit (injectable) |
| `AUTHORIZATION_FAILED` | 401 | Authorization failed (injectable) |
| `SYNTAX_ERROR` | 400 | COQL syntax error (injectable) |
| `DEPENDENT_FIELD_MISSING` | 400 | Dependent field not provided (injectable) |

**OAuth endpoint quirk:** `POST /oauth/v2/token` returns **HTTP 200** with `{"error": "invalid_client"}` on credential failures — not the CRM error envelope above.

### Rate limits

Every response includes these headers:

```
X-RATELIMIT-LIMIT: 5000
X-RATELIMIT-REMAINING: <credits left>
X-RATELIMIT-RESET: <unix timestamp when window resets>
```

- **Credits:** 5000 per rolling 60-second window (configurable via `MOCKZOHO_RATE_LIMIT_CREDITS` / `MOCKZOHO_RATE_LIMIT_WINDOW_SECONDS`)
- Each CRM call consumes 1 credit
- When exhausted → **HTTP 429** with `TOO_MANY_REQUESTS`
- Use `POST /__mock__/ratelimit` to set `remaining` or `limit` for testing
- Use `POST /__mock__/ratelimit/reset` to refill credits

**Two 429 scenarios:** `TOO_MANY_REQUESTS` = real credit exhaustion (auto); `API_LIMIT_EXCEEDED` = injectable fault only.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.reset_db_on_startup:
        drop_schema()
    create_schema()
    if settings.seed_on_startup:
        load_seeds()
    yield


app = FastAPI(
    title="Mock Zoho CRM API",
    version="1.0.0",
    description=DESCRIPTION,
    lifespan=lifespan,
    docs_url=None,
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


@app.get("/docs", include_in_schema=False)
async def custom_docs() -> HTMLResponse:
    return get_docs_html("/openapi.json", app.title)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(FaultInjectionMiddleware)

app.include_router(oauth_router)
app.include_router(coql_router, prefix="/crm/v3")
app.include_router(search_router, prefix="/crm/v3")
app.include_router(records_router, prefix="/crm/v3")
app.include_router(related_router, prefix="/crm/v3")
app.include_router(control_router)

app.mount("/presentations", StaticFiles(directory=str(Path(__file__).parent / "presentations")), name="presentations")

class SPAStaticFiles(StaticFiles):
    """StaticFiles with SPA fallback: unknown paths serve index.html
    so Vue Router history-mode routes (e.g. /ui/Cases) survive reloads."""

    async def get_response(self, path: str, scope):  # type: ignore[override]
        from starlette.exceptions import HTTPException as StarletteHTTPException

        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


_ui_dir = Path(__file__).parent / "static" / "ui"
if _ui_dir.exists():
    app.mount("/ui", SPAStaticFiles(directory=str(_ui_dir), html=True), name="ui")

    @app.get("/", include_in_schema=False)
    async def root_redirect() -> HTMLResponse:
        from starlette.responses import RedirectResponse
        return RedirectResponse(url="/ui/")


@app.exception_handler(ZohoAPIError)
async def zoho_error_handler(request: Request, exc: ZohoAPIError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.body())


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if exc.status_code == 405 and request.url.path.startswith("/crm/"):
        return JSONResponse(
            status_code=400,
            content=error_body(
                "INVALID_REQUEST_METHOD",
                "The http request method type is not a valid one",
                {},
            ),
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/health", tags=["Health"], summary="Health check")
def health() -> dict[str, str]:
    return {"status": "ok"}
