"""Search and COQL tests."""

def test_search_by_criteria(client, auth_headers):
    response = client.get(
        "/crm/v3/Cases/search?criteria=(Status:equals:Open)",
        headers=auth_headers,
    )
    assert response.status_code == 200
    records = response.json()["data"]
    assert len(records) == 1
    assert records[0]["Status"] == "Open"


def test_search_by_criteria_and(client, auth_headers):
    response = client.get(
        "/crm/v3/Cases/search?criteria=((Status:equals:Open)and(Priority:equals:Critical))",
        headers=auth_headers,
    )
    assert response.status_code == 200
    records = response.json()["data"]
    assert len(records) == 1
    assert records[0]["Priority"] == "Critical"


def test_search_no_results_returns_204(client, auth_headers):
    response = client.get(
        "/crm/v3/Cases/search?criteria=(Status:equals:NonExistent)",
        headers=auth_headers,
    )
    assert response.status_code == 204


def test_search_missing_param(client, auth_headers):
    response = client.get("/crm/v3/Cases/search", headers=auth_headers)
    assert response.status_code == 400
    assert response.json()["code"] == "REQUIRED_PARAM_MISSING"


def test_search_word(client, auth_headers):
    response = client.get(
        "/crm/v3/Cases/search?word=cooling",
        headers=auth_headers,
    )
    assert response.status_code == 200
    records = response.json()["data"]
    assert len(records) >= 1
    assert any("cooling" in r["Subject"].lower() for r in records)


def test_search_email(client, auth_headers):
    response = client.get(
        "/crm/v3/Cases/search?email=dana.levi@example.com",
        headers=auth_headers,
    )
    assert response.status_code == 200
    records = response.json()["data"]
    assert len(records) == 1
    assert records[0]["Email"] == "dana.levi@example.com"


def test_coql_basic(client, auth_headers):
    response = client.post(
        "/crm/v3/coql",
        headers=auth_headers,
        json={"select_query": "select Subject, Status from Cases where Status = 'Open' limit 10"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["info"]["count"] == 1
    assert body["data"][0]["Status"] == "Open"


def test_coql_with_and(client, auth_headers):
    response = client.post(
        "/crm/v3/coql",
        headers=auth_headers,
        json={
            "select_query": (
                "select Subject, Priority from Cases "
                "where (Status = 'Open' and Priority = 'Critical') limit 10"
            )
        },
    )
    assert response.status_code == 200
    records = response.json()["data"]
    assert len(records) == 1
    assert records[0]["Priority"] == "Critical"


def test_coql_no_results(client, auth_headers):
    response = client.post(
        "/crm/v3/coql",
        headers=auth_headers,
        json={"select_query": "select Subject from Cases where Status = 'NonExistent'"},
    )
    assert response.status_code == 204


def test_coql_invalid_module(client, auth_headers):
    response = client.post(
        "/crm/v3/coql",
        headers=auth_headers,
        json={"select_query": "select * from NonExistentModule"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_MODULE"


def test_coql_invalid_field(client, auth_headers):
    response = client.post(
        "/crm/v3/coql",
        headers=auth_headers,
        json={"select_query": "select BadField from Cases"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_QUERY"


def test_coql_order_by(client, auth_headers):
    response = client.post(
        "/crm/v3/coql",
        headers=auth_headers,
        json={
            "select_query": "select Subject, Priority from Cases order by Priority asc limit 10"
        },
    )
    assert response.status_code == 200
    records = response.json()["data"]
    priorities = [r["Priority"] for r in records]
    assert priorities == sorted(priorities, key=lambda p: p.lower())


def test_coql_numeric_comparison(client, auth_headers):
    response = client.post(
        "/crm/v3/coql",
        headers=auth_headers,
        json={"select_query": "select Name, Total_Cost from Labor_Costs where Total_Cost > 200"},
    )
    assert response.status_code == 200
    records = response.json()["data"]
    assert all(r["Total_Cost"] > 200 for r in records)


def test_coql_limit_exceeds_max(client, auth_headers):
    response = client.post(
        "/crm/v3/coql",
        headers=auth_headers,
        json={"select_query": "select Subject from Cases limit 500"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_QUERY"


def test_coql_offset_limit_syntax(client, auth_headers):
    response = client.post(
        "/crm/v3/coql",
        headers=auth_headers,
        json={"select_query": "select Subject, Status from Cases order by Modified_Time desc limit 0, 2"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["info"]["count"] == 2
    assert body["info"]["more_records"] is True


def test_coql_offset_limit_pagination(client, auth_headers):
    page1 = client.post(
        "/crm/v3/coql",
        headers=auth_headers,
        json={"select_query": "select Subject from Cases order by Modified_Time desc limit 0, 2"},
    )
    assert page1.status_code == 200
    assert page1.json()["info"]["count"] == 2

    page2 = client.post(
        "/crm/v3/coql",
        headers=auth_headers,
        json={"select_query": "select Subject from Cases order by Modified_Time desc limit 2, 2"},
    )
    assert page2.status_code == 200
    assert page2.json()["info"]["count"] == 2


def test_coql_too_many_fields(client, auth_headers):
    fields = ", ".join([f"Subject"] * 51)
    response = client.post(
        "/crm/v3/coql",
        headers=auth_headers,
        json={"select_query": f"select {fields} from Cases"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "LIMIT_EXCEEDED"
