"""OAuth token lifecycle tests."""

from app.auth.tokens import token_store


def test_refresh_token_grant(client):
    response = client.post(
        "/oauth/v2/token",
        data={
            "grant_type": "refresh_token",
            "client_id": "test_client",
            "client_secret": "test_secret",
            "refresh_token": "test_refresh",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] > 0
    assert "api_domain" in body
    assert "scope" in body


def test_client_credentials_grant(client):
    response = client.post(
        "/oauth/v2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "test_client",
            "client_secret": "test_secret",
            "scope": "ZohoCRM.modules.ALL",
            "soid": "test_org_id",
        },
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_client_credentials_missing_soid(client):
    response = client.post(
        "/oauth/v2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "test_client",
            "client_secret": "test_secret",
            "scope": "ZohoCRM.modules.ALL",
        },
    )
    assert response.status_code == 200
    assert response.json()["error"] == "invalid_request"


def test_missing_client_id(client):
    response = client.post(
        "/oauth/v2/token",
        data={"grant_type": "refresh_token", "client_secret": "test_secret"},
    )
    # Zoho returns 200 with error body
    assert response.status_code == 200
    assert "error" in response.json()


def test_invalid_grant_type(client):
    response = client.post(
        "/oauth/v2/token",
        data={"grant_type": "password", "client_id": "x", "client_secret": "y"},
    )
    assert response.status_code == 200
    assert response.json()["error"] == "unsupported_grant_type"


def test_token_works_for_auth(client, auth_headers):
    response = client.get("/crm/v3/Cases?fields=Subject", headers=auth_headers)
    assert response.status_code == 200


def test_missing_token_returns_401(client):
    response = client.get("/crm/v3/Cases")
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "INVALID_TOKEN"


def test_expired_token_returns_401(client, auth_headers):
    token_store.expire_all()
    response = client.get("/crm/v3/Cases", headers=auth_headers)
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_TOKEN"


def test_revoke_token(client):
    response = client.post(
        "/oauth/v2/token",
        data={
            "grant_type": "refresh_token",
            "client_id": "test_client",
            "client_secret": "test_secret",
            "refresh_token": "test_refresh",
        },
    )
    token = response.json()["access_token"]
    revoke = client.post("/oauth/v2/token/revoke", data={"token": token})
    assert revoke.status_code == 200
    assert revoke.json()["status"] == "success"
    # Token should no longer work
    response = client.get("/crm/v3/Cases", headers={"Authorization": f"Zoho-oauthtoken {token}"})
    assert response.status_code == 401


def test_json_body_token_request(client):
    response = client.post(
        "/oauth/v2/token",
        json={
            "grant_type": "refresh_token",
            "client_id": "test_client",
            "client_secret": "test_secret",
            "refresh_token": "test_refresh",
        },
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
