"""Composite API tests — envelopes, references, rollback, error codes."""

import pytest

COMPOSITE_URL = "/crm/v3/__composite_requests"


def _post(client, auth_headers, payload):
    return client.post(COMPOSITE_URL, headers=auth_headers, json=payload)


def _sub_results(response):
    return response.json()["__composite_requests"]


def test_create_then_get_by_reference(client, auth_headers):
    response = _post(
        client,
        auth_headers,
        {
            "__composite_requests": [
                {
                    "sub_request_id": "1",
                    "method": "POST",
                    "uri": "/crm/v3/Cases",
                    "body": {
                        "data": [
                            {
                                "Subject": "Composite case",
                                "Status": "Approved",
                                "Priority": "Low",
                                "Case_Type": "Repair",
                                "Customer_Name": "Ref Tester",
                            }
                        ]
                    },
                },
                {
                    "sub_request_id": "2",
                    "method": "GET",
                    "uri": "/crm/v3/Cases/@{1:$.data[0].details.id}",
                },
            ]
        },
    )
    assert response.status_code == 200
    results = _sub_results(response)
    assert len(results) == 2

    create = results[0]
    assert create["code"] == "SUCCESS"
    assert create["details"]["response"]["status_code"] == 201
    new_id = create["details"]["response"]["body"]["data"][0]["details"]["id"]

    get = results[1]
    assert get["code"] == "SUCCESS"
    assert get["details"]["response"]["status_code"] == 200
    record = get["details"]["response"]["body"]["data"][0]
    assert record["id"] == new_id
    assert record["Subject"] == "Composite case"


def test_reference_in_params_and_body(client, auth_headers):
    response = _post(
        client,
        auth_headers,
        {
            "parallel_execution": False,
            "__composite_requests": [
                {
                    "sub_request_id": "maker",
                    "method": "POST",
                    "uri": "/crm/v3/Cases",
                    "body": {
                        "data": [
                            {
                                "Subject": "Param ref case",
                                "Status": "Approved",
                                "Priority": "Low",
                                "Case_Type": "Repair",
                                "Customer_Name": "Ref Tester",
                            }
                        ]
                    },
                },
                {
                    "sub_request_id": "updater",
                    "method": "PUT",
                    "uri": "/crm/v3/Cases",
                    "body": {
                        "data": [
                            {
                                "id": "@{maker:$.data[0].details.id}",
                                "Status": "Closed",
                            }
                        ]
                    },
                },
                {
                    "sub_request_id": "lister",
                    "method": "GET",
                    "uri": "/crm/v3/Cases",
                    "params": {
                        "fields": "Subject,Status",
                        "ids": "@{maker:$.data[0].details.id}",
                    },
                },
            ]
        },
    )
    assert response.status_code == 200
    results = _sub_results(response)
    assert results[1]["details"]["response"]["status_code"] == 200
    listed = results[2]["details"]["response"]["body"]["data"]
    assert len(listed) == 1
    assert listed[0]["Status"] == "Closed"


def test_missing_composite_key(client, auth_headers):
    response = _post(client, auth_headers, {"rollback_on_fail": False})
    assert response.status_code == 400
    assert response.json()["code"] == "MANDATORY_NOT_FOUND"


def test_composite_requests_not_array(client, auth_headers):
    response = _post(client, auth_headers, {"__composite_requests": {"uri": "/crm/v3/Cases"}})
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_DATA"


def test_ambiguity_when_rollback_and_parallel(client, auth_headers):
    response = _post(
        client,
        auth_headers,
        {
            "rollback_on_fail": True,
            "parallel_execution": True,
            "__composite_requests": [
                {"method": "GET", "uri": "/crm/v3/Cases/4876000000200001"}
            ],
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == "AMBIGUITY_DURING_PROCESSING"


def test_more_than_five_sub_requests(client, auth_headers):
    response = _post(
        client,
        auth_headers,
        {
            "__composite_requests": [
                {"method": "GET", "uri": "/crm/v3/Cases/4876000000200001"}
                for _ in range(6)
            ]
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_DATA"


def test_rollback_on_fail_reverts_writes(client, auth_headers):
    response = _post(
        client,
        auth_headers,
        {
            "rollback_on_fail": True,
            "__composite_requests": [
                {
                    "sub_request_id": "1",
                    "method": "POST",
                    "uri": "/crm/v3/Cases",
                    "body": {
                        "data": [
                            {
                                "Subject": "Should be rolled back",
                                "Status": "Approved",
                                "Priority": "Low",
                                "Case_Type": "Repair",
                                "Customer_Name": "Rollback Tester",
                            }
                        ]
                    },
                },
                {
                    "sub_request_id": "2",
                    "method": "GET",
                    "uri": "/crm/v3/Cases/9999999999999999999",
                },
                {
                    "sub_request_id": "3",
                    "method": "GET",
                    "uri": "/crm/v3/Cases/4876000000200001",
                },
            ],
        },
    )
    assert response.status_code == 400
    results = _sub_results(response)
    assert results[0]["code"] == "ROLLBACK_PERFORMED"
    assert results[0]["details"]["rollbacked_by_sub_request_index"] == 1
    # The failing sub-request keeps its real (inner error) response.
    assert results[1]["code"] == "SUCCESS"
    assert results[1]["details"]["response"]["status_code"] == 404
    assert results[1]["details"]["response"]["body"]["code"] == "RESOURCE_NOT_FOUND"
    assert results[2]["code"] == "PROCESSING_STOPPED"

    # The record created by sub-request 1 must be gone.
    listing = client.get(
        "/crm/v3/Cases?fields=Subject", headers=auth_headers
    )
    subjects = [r["Subject"] for r in listing.json()["data"]]
    assert "Should be rolled back" not in subjects


def test_rollback_success_returns_200(client, auth_headers):
    response = _post(
        client,
        auth_headers,
        {
            "rollback_on_fail": True,
            "__composite_requests": [
                {
                    "method": "POST",
                    "uri": "/crm/v3/Cases",
                    "body": {
                        "data": [
                            {
                                "Subject": "Committed under rollback flag",
                                "Status": "Approved",
                                "Priority": "Low",
                                "Case_Type": "Repair",
                                "Customer_Name": "Rollback Tester",
                            }
                        ]
                    },
                },
                {"method": "GET", "uri": "/crm/v3/Cases/4876000000200001"},
            ],
        },
    )
    assert response.status_code == 200
    results = _sub_results(response)
    assert all(r["code"] == "SUCCESS" for r in results)


def test_forward_reference_sequential_invalid(client, auth_headers):
    response = _post(
        client,
        auth_headers,
        {
            "parallel_execution": False,
            "__composite_requests": [
                {
                    "sub_request_id": "1",
                    "method": "GET",
                    "uri": "/crm/v3/Cases/@{2:$.data[0].id}",
                },
                {
                    "sub_request_id": "2",
                    "method": "GET",
                    "uri": "/crm/v3/Cases/4876000000200001",
                },
            ],
        },
    )
    assert response.status_code == 207
    results = _sub_results(response)
    assert results[0]["code"] == "INVALID_REFERENCE"
    assert results[1]["code"] == "SUCCESS"


def test_forward_reference_parallel_resolves(client, auth_headers):
    """Parallel mode reorders: sub 1 references sub 2, which runs first."""
    response = _post(
        client,
        auth_headers,
        {
            "__composite_requests": [
                {
                    "sub_request_id": "1",
                    "method": "GET",
                    "uri": "/crm/v3/Cases/@{2:$.data[0].id}",
                },
                {
                    "sub_request_id": "2",
                    "method": "GET",
                    "uri": "/crm/v3/Cases/4876000000200001",
                },
            ]
        },
    )
    assert response.status_code == 200
    results = _sub_results(response)
    assert results[0]["code"] == "SUCCESS"
    assert results[0]["details"]["response"]["status_code"] == 200
    assert results[1]["code"] == "SUCCESS"


def test_looping_references_parallel(client, auth_headers):
    response = _post(
        client,
        auth_headers,
        {
            "__composite_requests": [
                {
                    "sub_request_id": "1",
                    "method": "GET",
                    "uri": "/crm/v3/Cases/@{2:$.data[0].id}",
                },
                {
                    "sub_request_id": "2",
                    "method": "GET",
                    "uri": "/crm/v3/Cases/@{1:$.data[0].id}",
                },
            ]
        },
    )
    results = _sub_results(response)
    assert all(r["code"] == "LOOPING_FOUND" for r in results)
    assert response.status_code == 400


def test_duplicate_sub_request_id(client, auth_headers):
    response = _post(
        client,
        auth_headers,
        {
            "__composite_requests": [
                {"sub_request_id": "dup", "method": "GET", "uri": "/crm/v3/Cases/4876000000200001"},
                {"sub_request_id": "dup", "method": "GET", "uri": "/crm/v3/Cases/4876000000200002"},
            ]
        },
    )
    results = _sub_results(response)
    assert results[0]["code"] == "SUCCESS"
    assert results[1]["code"] == "DUPLICATE_DATA"
    assert response.status_code == 207


def test_forbidden_header_in_sub_request(client, auth_headers):
    response = _post(
        client,
        auth_headers,
        {
            "__composite_requests": [
                {
                    "method": "GET",
                    "uri": "/crm/v3/Cases/4876000000200001",
                    "headers": {"Authorization": "Zoho-oauthtoken hack"},
                }
            ]
        },
    )
    results = _sub_results(response)
    assert results[0]["code"] == "INVALID_DATA"
    assert response.status_code == 400


def test_higher_version_uri_not_allowed(client, auth_headers):
    response = _post(
        client,
        auth_headers,
        {
            "__composite_requests": [
                {"method": "GET", "uri": "/crm/v8/Cases/4876000000200001"}
            ]
        },
    )
    results = _sub_results(response)
    assert results[0]["code"] == "NOT_ALLOWED"
    assert response.status_code == 400


def test_nested_composite_not_supported(client, auth_headers):
    response = _post(
        client,
        auth_headers,
        {
            "__composite_requests": [
                {"method": "POST", "uri": "/crm/v3/__composite_requests", "body": {}}
            ]
        },
    )
    results = _sub_results(response)
    assert results[0]["code"] == "NOT_SUPPORTED"


def test_inner_failure_does_not_stop_batch(client, auth_headers):
    """rollback_on_fail=false: inner errors don't stop later sub-requests."""
    response = _post(
        client,
        auth_headers,
        {
            "__composite_requests": [
                {"method": "GET", "uri": "/crm/v3/Cases/9999999999999999999"},
                {"method": "GET", "uri": "/crm/v3/Cases/4876000000200001"},
            ]
        },
    )
    assert response.status_code == 200
    results = _sub_results(response)
    assert results[0]["details"]["response"]["status_code"] == 404
    assert results[1]["details"]["response"]["status_code"] == 200


def test_requires_auth(client):
    response = client.post(
        COMPOSITE_URL,
        json={"__composite_requests": [{"method": "GET", "uri": "/crm/v3/Cases"}]},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_TOKEN"


@pytest.mark.parametrize("key", ["rollback_on_fail", "parallel_execution"])
def test_non_boolean_flags(client, auth_headers, key):
    response = _post(
        client,
        auth_headers,
        {
            key: "yes",
            "__composite_requests": [
                {"method": "GET", "uri": "/crm/v3/Cases/4876000000200001"}
            ],
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_DATA"
