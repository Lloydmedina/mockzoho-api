"""Error handling, rate limiting, and fault injection tests."""

def test_rate_limit_returns_429(client, auth_headers):
    # Set remaining credits to 2
    client.post("/__mock__/ratelimit", json={"remaining": 2})

    # First two calls succeed
    assert client.get("/crm/v3/Cases?fields=Subject", headers=auth_headers).status_code == 200
    assert client.get("/crm/v3/Cases?fields=Subject", headers=auth_headers).status_code == 200

    # Third call hits the limit
    response = client.get("/crm/v3/Cases?fields=Subject", headers=auth_headers)
    assert response.status_code == 429
    assert response.json()["code"] == "TOO_MANY_REQUESTS"

    # Verify rate limit headers
    assert "x-ratelimit-limit" in response.headers
    assert "x-ratelimit-remaining" in response.headers


def test_rate_limit_reset(client, auth_headers):
    client.post("/__mock__/ratelimit", json={"remaining": 0})
    response = client.get("/crm/v3/Cases?fields=Subject", headers=auth_headers)
    assert response.status_code == 429

    client.post("/__mock__/ratelimit/reset")
    response = client.get("/crm/v3/Cases?fields=Subject", headers=auth_headers)
    assert response.status_code == 200


def test_fault_injection_error(client, auth_headers):
    client.post("/__mock__/faults", json={"error_code": "INTERNAL_ERROR"})
    response = client.get("/crm/v3/Cases?fields=Subject", headers=auth_headers)
    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"


def test_fault_injection_clear(client, auth_headers):
    client.post("/__mock__/faults", json={"error_code": "INTERNAL_ERROR"})
    client.post("/__mock__/faults/clear")
    response = client.get("/crm/v3/Cases?fields=Subject", headers=auth_headers)
    assert response.status_code == 200


def test_fault_injection_path_filter(client, auth_headers):
    client.post("/__mock__/faults", json={"error_code": "INTERNAL_ERROR", "path_contains": "/Cases"})
    # Cases endpoint fails
    assert client.get("/crm/v3/Cases?fields=Subject", headers=auth_headers).status_code == 500
    # Products endpoint succeeds
    assert client.get("/crm/v3/Products?fields=Product_Name", headers=auth_headers).status_code == 200


def test_fault_injection_remaining_failures(client, auth_headers):
    client.post("/__mock__/faults", json={"error_code": "INTERNAL_ERROR", "remaining_failures": 1})
    # First call fails
    assert client.get("/crm/v3/Cases?fields=Subject", headers=auth_headers).status_code == 500
    # Second call succeeds (failures exhausted)
    assert client.get("/crm/v3/Cases?fields=Subject", headers=auth_headers).status_code == 200


def test_fault_injection_expire_tokens(client, auth_headers):
    client.post("/__mock__/faults", json={"expire_tokens": True})
    response = client.get("/crm/v3/Cases?fields=Subject", headers=auth_headers)
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_TOKEN"


def test_mock_reset(client, auth_headers):
    # Delete a record
    client.delete("/crm/v3/Cases/4876000000200001", headers=auth_headers)
    # Verify it's gone
    assert client.get("/crm/v3/Cases/4876000000200001", headers=auth_headers).status_code == 404

    # Reset
    client.post("/__mock__/reset")
    # Record should be back
    response = client.get("/crm/v3/Cases/4876000000200001", headers=auth_headers)
    assert response.status_code == 200


def test_mock_seed_custom(client, auth_headers):
    client.post(
        "/__mock__/seed",
        json={
            "module": "Cases",
            "records": [
                {
                    "id": "4876000000200099",
                    "Subject": "Custom seeded case",
                    "Status": "Open",
                    "Priority": "Medium",
                }
            ],
        },
    )
    response = client.get("/crm/v3/Cases/4876000000200099", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"][0]["Subject"] == "Custom seeded case"


def test_request_log(client, auth_headers):
    client.get("/crm/v3/Cases?fields=Subject", headers=auth_headers)
    client.post("/__mock__/faults", json={"error_code": "INTERNAL_ERROR"})
    client.get("/crm/v3/Cases?fields=Subject", headers=auth_headers)

    response = client.get("/__mock__/requests?limit=10")
    assert response.status_code == 200
    entries = response.json()["requests"]
    assert len(entries) >= 2
    assert entries[0]["method"] == "GET"
    assert "/crm/v3/Cases" in entries[0]["path"]


def test_mock_modules_endpoint(client):
    response = client.get("/__mock__/modules")
    assert response.status_code == 200
    modules = response.json()["modules"]
    assert "Cases" in modules
    assert "Visits" in modules
    assert "Products" in modules
    assert "Subject" in modules["Cases"]["fields"]
    assert "Subject" in modules["Cases"]["required"]


def test_pattern_not_matched(client, auth_headers):
    response = client.get(
        "/crm/v3/Cases?fields=Subject&sort_order=sideways", headers=auth_headers
    )
    assert response.status_code == 400
    assert response.json()["code"] == "PATTERN_NOT_MATCHED"


def test_invalid_request_method(client, auth_headers):
    response = client.patch("/crm/v3/Cases", headers=auth_headers)
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_REQUEST_METHOD"


def test_unable_to_parse_data_type(client, auth_headers):
    response = client.get("/crm/v3/Cases/not-a-number", headers=auth_headers)
    assert response.status_code == 400
    assert response.json()["code"] == "UNABLE_TO_PARSE_DATA_TYPE"


def test_invalid_url_pattern_now_404(client, auth_headers):
    response = client.get(
        "/crm/v3/Cases/4876000000200001/BogusList", headers=auth_headers
    )
    assert response.status_code == 404
    assert response.json()["code"] == "INVALID_URL_PATTERN"


def test_fault_injection_license_limit_exceeded(client, auth_headers):
    client.post("/__mock__/faults", json={"error_code": "LICENSE_LIMIT_EXCEEDED"})
    response = client.get("/crm/v3/Cases?fields=Subject", headers=auth_headers)
    assert response.status_code == 400
    assert response.json()["code"] == "LICENSE_LIMIT_EXCEEDED"


def test_fault_injection_feature_not_supported(client, auth_headers):
    client.post("/__mock__/faults", json={"error_code": "FEATURE_NOT_SUPPORTED"})
    response = client.get("/crm/v3/Cases?fields=Subject", headers=auth_headers)
    assert response.status_code == 403
    assert response.json()["code"] == "FEATURE_NOT_SUPPORTED"


def test_ratelimit_reset_uses_milliseconds(client, auth_headers):
    """X-RATELIMIT-RESET should be in epoch milliseconds (Zoho convention)."""
    client.post("/__mock__/ratelimit/reset")
    response = client.get("/crm/v3/Cases?fields=Subject", headers=auth_headers)
    reset_header = response.headers["x-ratelimit-reset"]
    # Milliseconds should be ~13 digits; seconds would be ~10
    assert len(reset_header) >= 13
    reset_ms = int(reset_header)
    import time
    now_ms = int(time.time() * 1000)
    # Reset should be within the next 60 seconds (60000 ms)
    assert reset_ms > now_ms
    assert reset_ms <= now_ms + 65000


def test_429_includes_retry_after_header(client, auth_headers):
    """429 responses must include a Retry-After header (seconds to wait)."""
    client.post("/__mock__/ratelimit", json={"remaining": 0})
    response = client.get("/crm/v3/Cases?fields=Subject", headers=auth_headers)
    assert response.status_code == 429
    assert "retry-after" in response.headers
    retry_after = int(response.headers["retry-after"])
    assert 1 <= retry_after <= 60
    client.post("/__mock__/ratelimit/reset")


def test_revoke_refresh_token_cascades_to_access_tokens(client):
    """Revoking a refresh token should invalidate all access tokens derived from it."""
    # Issue a token via refresh_token grant
    response = client.post(
        "/oauth/v2/token",
        data={
            "grant_type": "refresh_token",
            "client_id": "test_client",
            "client_secret": "test_secret",
            "refresh_token": "cascade_refresh_token",
        },
    )
    assert response.status_code == 200
    access_token = response.json()["access_token"]

    # Verify the access token works
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
    assert client.get("/crm/v3/Cases?fields=Subject", headers=headers).status_code == 200

    # Revoke the refresh token
    revoke = client.post(
        "/oauth/v2/token/revoke",
        data={"token": "cascade_refresh_token"},
    )
    assert revoke.status_code == 200
    assert revoke.json()["status"] == "success"

    # The access token should now be invalid (cascade revocation)
    response = client.get("/crm/v3/Cases?fields=Subject", headers=headers)
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_TOKEN"


def test_oauth_scope_mismatch_on_restricted_scope(client):
    """A token with scope limited to Products should get OAUTH_SCOPE_MISMATCH on Cases."""
    response = client.post(
        "/oauth/v2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "test_client",
            "client_secret": "test_secret",
            "scope": "ZohoCRM.modules.products.READ",
            "soid": "test_org_id",
        },
    )
    assert response.status_code == 200
    access_token = response.json()["access_token"]
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}

    # Accessing Products should work (scope covers it)
    products_response = client.get("/crm/v3/Products?fields=Product_Name", headers=headers)
    assert products_response.status_code == 200

    # Accessing Cases should fail with OAUTH_SCOPE_MISMATCH
    cases_response = client.get("/crm/v3/Cases?fields=Subject", headers=headers)
    assert cases_response.status_code == 401
    assert cases_response.json()["code"] == "OAUTH_SCOPE_MISMATCH"


def test_oauth_scope_all_covers_everything(client, auth_headers):
    """The default ZohoCRM.modules.ALL scope should cover all modules."""
    # auth_headers uses the default scope ZohoCRM.modules.ALL,ZohoCRM.settings.ALL
    for module in ["Cases", "Visits", "Products"]:
        response = client.get(f"/crm/v3/{module}?fields=Subject", headers=auth_headers)
        # Should not get OAUTH_SCOPE_MISMATCH (may get 200 or 204)
        if response.status_code == 401:
            assert response.json()["code"] != "OAUTH_SCOPE_MISMATCH"
