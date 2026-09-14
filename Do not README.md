# Mock Zoho CRM API

A high-fidelity mock of the **Zoho CRM v3 REST API** for local development and testing. Built with FastAPI + SQLite.

## Why?

When the real Zoho CRM isn't ready (no credentials, API not provisioned), this mock lets your adapter code run against a real HTTP surface that behaves like Zoho — same envelopes, same error codes, same edge cases (like `204 No Content` on empty reads). When Zoho is ready, you switch two env vars and your code works unmodified.

## Quick start

### Option A: Docker

```bash
docker compose up --build
```

### Option B: Local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8090
```

### Option C: Direct

```bash
pip install -r requirements.txt
python -c "import uvicorn; uvicorn.run('app.main:app', host='0.0.0.0', port=8090)"
```

Then open **[http://localhost:8090/docs](http://localhost:8090/docs)** for Swagger UI.

## Pointing your app here

Set these env vars in `tadiran-force-app-api` (or any Zoho CRM client):

```env
ZOHO_BASE_URL=http://localhost:8090/crm/v3
ZOHO_ACCOUNTS_URL=http://localhost:8090
```

No other code changes needed.

## Available modules

| Module | API Name | Description |
|--------|----------|-------------|
| Cases | `Cases` | Repair/maintenance cases |
| Visits | `Visits` | Technician site visits |
| Products | `Products` | Product catalog + spare parts |
| Labor Costs | `Labor_Costs` | Labor billing lines |
| Spare Parts | `Spare_Parts` | Parts used in repairs |
| Case Actions | `Case_Actions` | Case activity log |

View the full schema at `GET /__mock__/modules` or in the Swagger UI description.

## Curl walkthrough

### 1. Get an access token

```bash
curl -s -X POST http://localhost:8090/oauth/v2/token \
  -d "grant_type=refresh_token" \
  -d "client_id=test_client" \
  -d "client_secret=test_secret" \
  -d "refresh_token=test_refresh" | python -m json.tool
```

Save the `access_token` value. Set it as a variable:

```bash
TOKEN="1000.xxxx.yyyy"   # paste your token here
```

### 2. List cases

```bash
curl -s "http://localhost:8090/crm/v3/Cases?fields=Subject,Status,Priority" \
  -H "Authorization: Zoho-oauthtoken $TOKEN" | python -m json.tool
```

### 3. Create a visit

```bash
curl -s -X POST http://localhost:8090/crm/v3/Visits \
  -H "Authorization: Zoho-oauthtoken $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "data": [{
      "Name": "Emergency visit",
      "Case": {"id": "4876000000200001"},
      "Visit_Date": "2026-09-12T09:00:00+08:00",
      "Status": "Scheduled",
      "Visit_Type": "Repair",
      "Technician": "Yossi Bar"
    }]
  }' | python -m json.tool
```

### 4. Search with COQL

```bash
curl -s -X POST http://localhost:8090/crm/v3/coql \
  -H "Authorization: Zoho-oauthtoken $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "select_query": "select Subject, Status, Priority from Cases where Status = '\''Open'\'' order by Priority desc limit 10"
  }' | python -m json.tool
```

### 5. Get related records (visits for a case)

```bash
curl -s http://localhost:8090/crm/v3/Cases/4876000000200001/Visits \
  -H "Authorization: Zoho-oauthtoken $TOKEN" | python -m json.tool
```

### 6. Trigger rate limiting (429)

```bash
# Set remaining credits to 1
curl -s -X POST http://localhost:8090/__mock__/ratelimit \
  -H "Content-Type: application/json" \
  -d '{"remaining": 1}'

# First call succeeds
curl -s "http://localhost:8090/crm/v3/Cases?fields=Subject" \
  -H "Authorization: Zoho-oauthtoken $TOKEN"

# Second call gets 429
curl -s "http://localhost:8090/crm/v3/Cases?fields=Subject" \
  -H "Authorization: Zoho-oauthtoken $TOKEN" | python -m json.tool
```

### 7. Inject faults

```bash
# Force all CRM calls to return 500
curl -s -X POST http://localhost:8090/__mock__/faults \
  -H "Content-Type: application/json" \
  -d '{"error_code": "INTERNAL_ERROR"}'

# Clear faults
curl -s -X POST http://localhost:8090/__mock__/faults/clear
```

### 8. Reset to seed state

```bash
curl -s -X POST http://localhost:8090/__mock__/reset | python -m json.tool
```

## Mock control plane

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/__mock__/reset` | POST | Wipe DB and reload seed fixtures |
| `/__mock__/seed` | POST | Load custom fixture data |
| `/__mock__/faults` | POST | Configure fault injection |
| `/__mock__/faults` | GET | View current fault config |
| `/__mock__/faults/clear` | POST | Clear all faults |
| `/__mock__/ratelimit` | POST | Configure rate limit credits |
| `/__mock__/ratelimit` | GET | View rate limit state |
| `/__mock__/ratelimit/reset` | POST | Reset credits to full |
| `/__mock__/requests` | GET | View recent request log |
| `/__mock__/requests/clear` | POST | Clear request log |
| `/__mock__/modules` | GET | View module schemas |
| `/__mock__/health` | GET | Health check |

## Zoho contract details replicated

- `Authorization: Zoho-oauthtoken <token>` header auth
- `{"data": [...], "info": {...}}` list envelopes
- `{"data": [{"code": "SUCCESS", "details": {"id": "..."}}]}` write responses
- **HTTP 204 No Content** on empty list/search reads (common client bug source)
- **HTTP 207 Multi-Status** on partial success in bulk writes
- **HTTP 404** with `RESOURCE_NOT_FOUND` on single-record GET for non-existent IDs
- Per-record success/error results in bulk writes
- 19-digit numeric record IDs
- ISO 8601 timestamps with timezone offset
- Pagination via `page` + `per_page` with `more_records` flag
- Error codes: `INVALID_TOKEN`, `INVALID_MODULE`, `MANDATORY_NOT_FOUND`, `INVALID_DATA`, `RESOURCE_NOT_FOUND`, `TOO_MANY_REQUESTS`, and more
- Rate limit headers: `X-RATELIMIT-LIMIT`, `X-RATELIMIT-REMAINING`, `X-RATELIMIT-RESET`
- COQL query language subset (`SELECT ... FROM ... WHERE ... GROUP BY ... ORDER BY ... LIMIT ...`)
- COQL `LIMIT offset, limit` pagination syntax (Zoho-style) and `LIMIT n` simple syntax
- COQL enforces max 50 fields in SELECT and max 200 in LIMIT
- Module `/search` with `criteria`, `email`, `phone`, `word` parameters

## Customizing the module schema

All module field definitions live in `app/modules/registry.py`. When you get the real `BaseCRMAdapter` contract, update the `FieldSpec` entries there and every route, validator, seed loader, and COQL query follows automatically.

## Running tests

```bash
pip install -r requirements.txt
pytest -v
```

## Project structure

```
app/
  main.py              # FastAPI app, lifespan, router wiring
  config.py            # Settings (env vars)
  db.py                # SQLite engine/session
  models.py            # Generic Record table
  repository.py        # Storage access layer
  utils.py             # ID generation, timestamps
  schemas/zoho.py      # Response envelopes, error catalog
  modules/registry.py   # Module field definitions (edit me!)
  modules/validation.py# Payload validation driven by registry
  auth/                # OAuth token endpoints + auth guard
  api/                 # CRUD, search, COQL, related, control routes
  middleware/          # Rate limiting + fault injection
seeds/data.py          # Seed fixtures as Python dicts
tests/                 # pytest suite
```
