"""Functions-execute tests — the calculate_visit_total pricing simulation."""


def _payload() -> dict:
    return {
        "arguments": {
            "technician_count": 1,
            "technician_hours": 2.0,
            "helper_hours": 1.0,
            "kilometers_traveled": 40.0,
            "gas_type": "R32",
            "gas_quantity_kg": 1.0,
            "meal_expense": 15.0,
            "other_expenses": 10.0,
            "expense_description": "Parking toll",
        }
    }


def test_execute_pricing_function(client, auth_headers):
    response = client.post(
        "/crm/v3/functions/calculate_visit_total/actions/execute?auth_type=oauth",
        json=_payload(),
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "success"
    # 2.0*45 + 1.0*30 + 40*0.5 + 1.0*25 + 15 + 10 = 190
    assert body["details"]["output"] == "190.00"


def test_execute_pricing_function_query_args(client, auth_headers):
    response = client.post(
        "/crm/v3/functions/calculate_visit_total/actions/execute"
        "?auth_type=oauth&technician_hours=1.0",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["details"]["output"] == "45.00"


def test_execute_unknown_function(client, auth_headers):
    response = client.post(
        "/crm/v3/functions/no_such_function/actions/execute?auth_type=oauth",
        json=_payload(),
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert response.json()["code"] == "INVALID_URL_PATTERN"


def test_execute_requires_token(client):
    response = client.post(
        "/crm/v3/functions/calculate_visit_total/actions/execute?auth_type=oauth",
        json=_payload(),
    )
    assert response.status_code == 401


def test_execute_with_apikey_auth(client):
    """auth_type=apikey authenticates via zapikey param, no OAuth header needed."""
    response = client.post(
        "/crm/v3/functions/calculate_visit_total/actions/execute"
        "?auth_type=apikey&zapikey=1003.testkey&technician_hours=1.0",
    )
    assert response.status_code == 200
    assert response.json()["details"]["output"] == "45.00"
