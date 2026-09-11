"""Mock Zoho CRM API — FastAPI application factory."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

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
from app.schemas.zoho import ZohoAPIError

DESCRIPTION = """
## Mock Zoho CRM API

A high-fidelity mock of the **Zoho CRM v3 REST API** for local development and testing.

### Getting started

1. **Get a token** — `POST /oauth/v2/token` with `grant_type=refresh_token`,
   `client_id`, `client_secret`, `refresh_token` (any values work unless
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


@app.exception_handler(ZohoAPIError)
async def zoho_error_handler(request: Request, exc: ZohoAPIError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.body())


@app.get("/health", tags=["Health"], summary="Health check")
def health() -> dict[str, str]:
    return {"status": "ok"}
