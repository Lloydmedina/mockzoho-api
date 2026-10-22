# Mock Zoho CRM API

A high-fidelity mock of the **Zoho CRM v3 REST API** for local development and testing. Built with FastAPI + SQLite.

## Running it

### Docker (recommended)

```bash
docker compose up -d --build
```

The container listens on port **8090** internally and is published on the host at **http://localhost:8091**.

### Without Docker

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8090
```

## Where things live

| What | URL (docker) |
|------|--------------|
| CRM API | `http://localhost:8091/crm/v3` |
| OAuth token endpoint | `http://localhost:8091/oauth/v2/token` |
| Swagger docs | `http://localhost:8091/docs` |
| Admin UI | `http://localhost:8091/ui/` |
| Health check | `http://localhost:8091/health` |

## Getting a token

Any credentials are accepted by default (unless `MOCKZOHO_EXPECTED_*` env vars are set). For local testing use:

- `client_id=1000.MOCKCLIENTID`
- `client_secret=mock_client_secret`
- `refresh_token=1000.mockrefreshtoken.refresh`

```bash
curl -s -X POST http://localhost:8091/oauth/v2/token \
  -d grant_type=refresh_token \
  -d client_id=1000.MOCKCLIENTID \
  -d client_secret=mock_client_secret \
  -d refresh_token=1000.mockrefreshtoken.refresh
```

In Swagger UI (`/docs`), click **Authorize** and paste `Zoho-oauthtoken <access_token>`.

## Connecting app-api (usage setup)

Set these in `app-api/.env`:

```dotenv
CRM_PROVIDER=zoho
ZOHO_BASE_URL=http://localhost:8091/crm/v3
ZOHO_ACCOUNTS_URL=http://localhost:8091
ZOHO_CLIENT_ID=1000.MOCKCLIENTID
ZOHO_CLIENT_SECRET=mock_client_secret
ZOHO_REFRESH_TOKEN=1000.mockrefreshtoken.refresh
```

Restart app-api after editing `.env` (`uvicorn --reload` only watches `.py` files).

Verify with:

```bash
curl -s http://localhost:3000/api/v1/zoho/connectivity -H "Authorization: Bearer <app-api-token>"
# expected: "status": "ok", oauth.ok=true, api.ok=true
```

## Getting an app-api token for Swagger testing

Repair endpoints filter records by the JWT `sub` claim (the technician id). **Use an app-api token, not an admin-api token** — admin tokens carry `sub` as a JSON string (`{"id": "..."}`) which matches no technician, so endpoints return empty lists.

With `OTP_ENABLE_BYPASS=true` in app-api `.env`, one call mints a dev token (no SMS, no `send-code` needed):

```bash
curl -s -X POST http://localhost:3000/api/v1/auth/verify-code \
  -H 'Content-Type: application/json' \
  -d '{"phone_number": "+393481234567", "code": "0000",
       "device_id": "swagger", "client_id": "web", "client_version": "1.0.0"}'
```

Use the returned `token` in Swagger **Authorize** on app-api (`http://localhost:3000/docs`).

## Seeded data

| Technician | ID | Cases |
|------------|----|-------|
| Yossi Bar (TECHNICIAN_1 — matches the seeded dev user `+393481234567`) | `21f3f68b-9c67-498c-b9bb-d25e395ec999` | `CASE-IT-101124`, `CASE-IT-101126` |
| Avi Sade (TECHNICIAN_2) | `b642fb08-7959-5e71-9de2-d70705ecc3e0` | `CASE-IT-101125`, `CASE-IT-101127` |

So `GET /api/v1/repair/cases/it` with the dev token above returns **2 cases**.

## Mock control plane

- `POST /__mock__/reset` — restore database to seed state
- `POST /__mock__/faults` — inject errors, latency, or token expiry
- `POST /__mock__/ratelimit` — configure rate limit credits
- `GET /__mock__/requests` — view recent request log
- `GET /__mock__/modules` — view module schemas

## Notes

- Tokens, rate-limit credits, fault state, and the request log live **in memory** — run a single uvicorn worker, and expect tokens to die on restart (issue a fresh one).
- Records persist in `mockzoho.db` (SQLite). `POST /__mock__/reset` restores seed state.
