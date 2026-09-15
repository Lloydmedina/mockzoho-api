# Mock Zoho CRM API

A high-fidelity mock of the **Zoho CRM v3 REST API** for local development and testing. Built with FastAPI + SQLite.

## Getting a token

Any credentials are accepted by default. For local testing use:

- `client_id=1000.MOCKCLIENTID`
- `client_secret=mock_client_secret`
- `refresh_token=1000.mockrefreshtoken.refresh`

```bash
curl -s -X POST http://localhost:8090/oauth/v2/token -d grant_type=refresh_token -d client_id=1000.MOCKCLIENTID -d client_secret=mock_client_secret -d refresh_token=1000.mockrefreshtoken.refresh
```

In Swagger UI (`/docs`), click **Authorize** and paste `Zoho-oauthtoken <access_token>`.