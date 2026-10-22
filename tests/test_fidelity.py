"""Fidelity fixes — Zoho envelope on framework errors, field validation,
COQL hardening, criteria/COQL parsing edge cases, system fields."""

import json


def test_bad_query_param_type_returns_zoho_envelope(client, auth_headers):
    """Non-integer `page` must produce a Zoho error body, not a FastAPI 422."""
    response = client.get("/crm/v3/Cases?fields=Subject&page=abc", headers=auth_headers)
    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "error"
    assert body["code"] == "INVALID_QUERY_PARAM"


def test_bad_body_type_returns_zoho_envelope(client, auth_headers):
    response = client.post(
        "/crm/v3/Cases",
        headers=auth_headers,
        json={"data": "not-a-list"},
    )
    assert response.status_code == 400
    assert response.json()["status"] == "error"


def test_unknown_crm_path_returns_invalid_url_pattern(client, auth_headers):
    response = client.get("/crm/v3/Cases/4876000000200001/Visits/extra/path", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["code"] == "INVALID_URL_PATTERN"


def test_deeply_nested_unknown_path(client, auth_headers):
    response = client.get("/crm/v3/a/b/c/d", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["code"] == "INVALID_URL_PATTERN"


def test_unknown_field_in_fields_param(client, auth_headers):
    response = client.get("/crm/v3/Cases?fields=Subject,NotAField", headers=auth_headers)
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_DATA"


def test_fields_param_over_50_fields(client, auth_headers):
    fields = ",".join(["Subject"] * 51)
    response = client.get(f"/crm/v3/Cases?fields={fields}", headers=auth_headers)
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_DATA"


def test_insert_ignores_client_supplied_id(client, auth_headers):
    """Real Zoho ignores `id` on insert — no PK collision, no 500."""
    for _ in range(2):
        response = client.post(
            "/crm/v3/Cases",
            headers=auth_headers,
            json={"data": [{"id": "4876000000200001", "Subject": "id-supplying case"}]},
        )
        assert response.status_code == 201
        result = response.json()["data"][0]
        assert result["code"] == "SUCCESS"
        assert result["details"]["id"] != "4876000000200001"


def test_single_put_rejects_mismatched_body_id(client, auth_headers):
    response = client.put(
        "/crm/v3/Cases/4876000000200001",
        headers=auth_headers,
        json={"data": [{"id": "4876000000200002", "Status": "Closed"}]},
    )
    assert response.status_code == 400


def test_single_put_allows_matching_body_id(client, auth_headers):
    response = client.put(
        "/crm/v3/Cases/4876000000200001",
        headers=auth_headers,
        json={"data": [{"id": "4876000000200001", "Status": "Closed"}]},
    )
    assert response.status_code == 200


def test_delete_non_numeric_ids(client, auth_headers):
    response = client.delete("/crm/v3/Cases?ids=abc", headers=auth_headers)
    assert response.status_code == 400
    assert response.json()["code"] == "UNABLE_TO_PARSE_DATA_TYPE"


def test_list_non_numeric_ids(client, auth_headers):
    response = client.get("/crm/v3/Cases?fields=Subject&ids=abc", headers=auth_headers)
    assert response.status_code == 400
    assert response.json()["code"] == "UNABLE_TO_PARSE_DATA_TYPE"


def test_bulk_update_non_numeric_id(client, auth_headers):
    response = client.put(
        "/crm/v3/Cases",
        headers=auth_headers,
        json={"data": [{"id": "abc", "Status": "Closed"}]},
    )
    assert response.status_code == 400
    assert response.json()["data"][0]["code"] == "UNABLE_TO_PARSE_DATA_TYPE"


def test_coql_group_by_rejected(client, auth_headers):
    response = client.post(
        "/crm/v3/coql",
        headers=auth_headers,
        json={"select_query": "select Status from Cases group by Status"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_QUERY"


def test_coql_non_numeric_limit(client, auth_headers):
    response = client.post(
        "/crm/v3/coql",
        headers=auth_headers,
        json={"select_query": "select Subject from Cases limit abc"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_QUERY"


def test_coql_negative_limit(client, auth_headers):
    response = client.post(
        "/crm/v3/coql",
        headers=auth_headers,
        json={"select_query": "select Subject from Cases limit -5"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_QUERY"


def test_coql_three_part_limit(client, auth_headers):
    response = client.post(
        "/crm/v3/coql",
        headers=auth_headers,
        json={"select_query": "select Subject from Cases limit 1,2,3"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_QUERY"


def test_criteria_value_containing_and(client, auth_headers):
    """'and' inside a leaf value must not split the expression."""
    client.post(
        "/crm/v3/Cases",
        headers=auth_headers,
        json={"data": [{"Subject": "Replace parts and labor", "Status": "Approved"}]},
    )
    response = client.get(
        "/crm/v3/Cases/search",
        params={"criteria": "(Subject:contains:parts and labor)"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["Subject"] == "Replace parts and labor"


def test_coql_quoted_and_in_value(client, auth_headers):
    """'and' inside a quoted COQL value must not split the WHERE clause."""
    client.post(
        "/crm/v3/Cases",
        headers=auth_headers,
        json={"data": [{"Subject": "x and y", "Status": "Approved"}]},
    )
    response = client.post(
        "/crm/v3/coql",
        headers=auth_headers,
        json={"select_query": "select Subject from Cases where Subject = 'x and y'"},
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["Subject"] == "x and y"


def test_if_modified_since_z_suffix(client, auth_headers):
    """A Z-suffixed (UTC) If-Modified-Since must still filter correctly."""
    response = client.get(
        "/crm/v3/Cases?fields=Subject",
        headers={**auth_headers, "If-Modified-Since": "2000-01-01T00:00:00Z"},
    )
    assert response.status_code == 200
    assert len(response.json()["data"]) > 0


def test_if_modified_since_future_returns_304(client, auth_headers):
    response = client.get(
        "/crm/v3/Cases?fields=Subject",
        headers={**auth_headers, "If-Modified-Since": "2999-01-01T00:00:00Z"},
    )
    assert response.status_code == 304


def test_if_modified_since_invalid(client, auth_headers):
    response = client.get(
        "/crm/v3/Cases?fields=Subject",
        headers={**auth_headers, "If-Modified-Since": "not-a-date"},
    )
    assert response.status_code == 400


def test_record_includes_system_fields(client, auth_headers):
    response = client.get("/crm/v3/Cases/4876000000200001", headers=auth_headers)
    record = response.json()["data"][0]
    assert record["Owner"]["id"]
    assert record["Created_By"]["id"]
    assert record["Modified_By"]["id"]
    assert "$approval" in record


def test_fault_injection_does_not_hit_oauth(client):
    """Faults are scoped to /crm/ — the token endpoint must stay reachable."""
    client.post("/__mock__/faults", json={"error_code": "INTERNAL_ERROR"})
    response = client.post(
        "/oauth/v2/token",
        data={
            "grant_type": "refresh_token",
            "client_id": "x",
            "client_secret": "y",
            "refresh_token": "z",
        },
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_function_execute_get(client, auth_headers):
    response = client.get(
        "/crm/v3/functions/calculate_visit_total/actions/execute"
        "?auth_type=oauth&technician_hours=2.0",
        headers=auth_headers,
    )
    assert response.status_code == 200
    output = json.loads(response.json()["details"]["output"])
    assert output["total_amount"] == 90.0


def test_case_number_monotonic(client, auth_headers):
    """Auto-numbered Case_Number values must not be reused after deletes."""
    created = client.post(
        "/crm/v3/Cases",
        headers=auth_headers,
        json={"data": [{"Subject": "auto 1"}]},
    )
    first = created.json()["data"][0]["details"]["id"]
    number1 = client.get(
        f"/crm/v3/Cases/{first}", headers=auth_headers
    ).json()["data"][0]["Case_Number"]

    client.delete(f"/crm/v3/Cases/{first}", headers=auth_headers)

    created2 = client.post(
        "/crm/v3/Cases",
        headers=auth_headers,
        json={"data": [{"Subject": "auto 2"}]},
    )
    second = created2.json()["data"][0]["details"]["id"]
    number2 = client.get(
        f"/crm/v3/Cases/{second}", headers=auth_headers
    ).json()["data"][0]["Case_Number"]

    assert number1 != number2
    assert number1.startswith("CASE-") and number2.startswith("CASE-")
