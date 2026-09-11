"""Shared test fixtures."""

import pytest
from fastapi.testclient import TestClient

from app.api.control import load_seeds
from app.auth.tokens import token_store
from app.db import create_schema, drop_schema, engine
from app.middleware.faults import fault_state, request_log
from app.middleware.ratelimit import credit_window
from app.models import Base


@pytest.fixture(autouse=True)
def reset_state():
    """Reset DB, tokens, faults, and rate limit before each test."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    load_seeds()
    token_store.clear()
    fault_state.reset()
    credit_window.reset()
    request_log.clear()
    yield
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


@pytest.fixture()
def client():
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def auth_headers(client):
    """Get a valid access token and return Authorization headers."""
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
    token = response.json()["access_token"]
    return {"Authorization": f"Zoho-oauthtoken {token}"}
