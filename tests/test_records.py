"""Record CRUD tests — envelopes, 204s, validation, pagination, bulk writes."""

from app.config import settings


def test_list_cases(client, auth_headers):
    response = client.get("/crm/v3/Cases?fields=Subject,Status,Priority", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "info" in body
    assert len(body["data"]) == 4
    assert body["info"]["count"] == 4
    assert body["info"]["page"] == 1


def test_list_cases_fields_projection(client, auth_headers):
    response = client.get("/crm/v3/Cases?fields=Subject,Status", headers=auth_headers)
    assert response.status_code == 200
    records = response.json()["data"]
    for record in records:
        assert "Subject" in record
        assert "Status" in record
        # id is always included
        assert "id" in record


def test_get_single_record(client, auth_headers):
    response = client.get("/crm/v3/Cases/4876000000200001", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["Subject"] == "AC unit not cooling - capacitor failure"


def test_get_nonexistent_returns_404(client, auth_headers):
    response = client.get("/crm/v3/Cases/9999999999999999999", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["code"] == "RESOURCE_NOT_FOUND"


def test_create_record(client, auth_headers):
    response = client.post(
        "/crm/v3/Cases",
        headers=auth_headers,
        json={
            "data": [
                {
                    "Subject": "New test case",
                    "Status": "Open",
                    "Priority": "Medium",
                }
            ]
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["data"][0]["code"] == "SUCCESS"
    assert "id" in body["data"][0]["details"]
    assert body["data"][0]["message"] == "record added"


def test_create_missing_required_field(client, auth_headers):
    response = client.post(
        "/crm/v3/Cases",
        headers=auth_headers,
        json={"data": [{"Status": "Open"}]},
    )
    assert response.status_code == 400
    result = response.json()["data"][0]
    assert result["code"] == "MANDATORY_NOT_FOUND"
    assert result["details"]["api_name"] == "Subject"


def test_create_invalid_picklist(client, auth_headers):
    response = client.post(
        "/crm/v3/Cases",
        headers=auth_headers,
        json={"data": [{"Subject": "Test", "Status": "NotARealStatus"}]},
    )
    assert response.status_code == 400
    assert response.json()["data"][0]["code"] == "INVALID_DATA"


def test_update_record(client, auth_headers):
    response = client.put(
        "/crm/v3/Cases/4876000000200001",
        headers=auth_headers,
        json={"data": [{"Status": "Closed", "Resolution": "Fixed"}]},
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["code"] == "SUCCESS"
    assert response.json()["data"][0]["message"] == "record updated"

    # Verify the update persisted
    get_response = client.get("/crm/v3/Cases/4876000000200001", headers=auth_headers)
    record = get_response.json()["data"][0]
    assert record["Status"] == "Closed"
    assert record["Resolution"] == "Fixed"


def test_update_nonexistent(client, auth_headers):
    response = client.put(
        "/crm/v3/Cases/9999999999999999999",
        headers=auth_headers,
        json={"data": [{"Status": "Closed"}]},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "RESOURCE_NOT_FOUND"


def test_delete_record(client, auth_headers):
    response = client.delete("/crm/v3/Cases/4876000000200001", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"][0]["code"] == "SUCCESS"

    # Verify it's gone
    get_response = client.get("/crm/v3/Cases/4876000000200001", headers=auth_headers)
    assert get_response.status_code == 404


def test_delete_nonexistent(client, auth_headers):
    response = client.delete("/crm/v3/Cases/9999999999999999999", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["code"] == "RESOURCE_NOT_FOUND"


def test_bulk_delete(client, auth_headers):
    response = client.delete(
        "/crm/v3/Cases?ids=4876000000200001,4876000000200002",
        headers=auth_headers,
    )
    assert response.status_code == 200
    results = response.json()["data"]
    assert len(results) == 2
    assert all(r["code"] == "SUCCESS" for r in results)


def test_upsert_insert_new(client, auth_headers):
    response = client.post(
        "/crm/v3/Cases/upsert",
        headers=auth_headers,
        json={
            "data": [{"Subject": "Upserted case", "Status": "Open"}],
            "duplicate_check_fields": ["Subject"],
        },
    )
    assert response.status_code == 200
    result = response.json()["data"][0]
    assert result["code"] == "SUCCESS"
    assert result["action"] == "insert"


def test_upsert_update_existing(client, auth_headers):
    response = client.post(
        "/crm/v3/Cases/upsert",
        headers=auth_headers,
        json={
            "data": [{"id": "4876000000200001", "Status": "Closed"}],
        },
    )
    assert response.status_code == 200
    result = response.json()["data"][0]
    assert result["code"] == "SUCCESS"
    assert result["action"] == "update"


def test_invalid_module(client, auth_headers):
    response = client.get("/crm/v3/NonExistentModule?fields=Subject", headers=auth_headers)
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_MODULE"


def test_pagination(client, auth_headers):
    response = client.get("/crm/v3/Cases?fields=Subject&page=1&per_page=2", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["info"]["count"] == 2
    assert body["info"]["more_records"] is True

    page2 = client.get("/crm/v3/Cases?fields=Subject&page=2&per_page=2", headers=auth_headers)
    assert page2.status_code == 200
    assert page2.json()["info"]["more_records"] is False


def test_per_page_exceeds_max(client, auth_headers):
    response = client.get(f"/crm/v3/Cases?fields=Subject&per_page={settings.max_per_page + 1}", headers=auth_headers)
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_QUERY_PARAM"


def test_list_missing_fields_param(client, auth_headers):
    response = client.get("/crm/v3/Cases", headers=auth_headers)
    assert response.status_code == 400
    assert response.json()["code"] == "REQUIRED_PARAM_MISSING"


def test_empty_data_rejected(client, auth_headers):
    response = client.post("/crm/v3/Cases", headers=auth_headers, json={"data": []})
    assert response.status_code == 400
    assert response.json()["code"] == "REQUIRED_PARAM_MISSING"


def test_partial_success_returns_207(client, auth_headers):
    response = client.post(
        "/crm/v3/Cases",
        headers=auth_headers,
        json={
            "data": [
                {"Subject": "Good case", "Status": "Open"},
                {"Subject": "Bad case", "Status": "NotARealStatus"},
            ]
        },
    )
    assert response.status_code == 207
    results = response.json()["data"]
    assert results[0]["code"] == "SUCCESS"
    assert results[1]["code"] == "INVALID_DATA"


def test_write_response_includes_approval_state(client, auth_headers):
    response = client.post(
        "/crm/v3/Cases",
        headers=auth_headers,
        json={"data": [{"Subject": "Test", "Status": "Open"}]},
    )
    assert response.status_code == 201
    details = response.json()["data"][0]["details"]
    assert details["$approval_state"] == "approved"


def test_related_records(client, auth_headers):
    response = client.get(
        "/crm/v3/Cases/4876000000200001/Visits",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["info"]["count"] == 2
    assert all(v["Case"]["id"] == "4876000000200001" for v in body["data"])


def test_related_records_empty(client, auth_headers):
    response = client.get(
        "/crm/v3/Cases/4876000000200004/Visits",
        headers=auth_headers,
    )
    assert response.status_code == 204


def test_related_records_bad_parent(client, auth_headers):
    response = client.get(
        "/crm/v3/Cases/9999999999999999999/Visits",
        headers=auth_headers,
    )
    assert response.status_code == 204
