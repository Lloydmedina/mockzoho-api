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
