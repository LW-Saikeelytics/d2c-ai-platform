
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app


# =====================================================
# PHASE 9.11.3B - RUN HISTORY QUERY API TEST
# =====================================================

ENDPOINT = "/api/v1/run-history"

KNOWN_RUN = (
    "api_run_ebaaf56bd9b14c1d9fca1af532387316"
)

LEGACY_RUN = (
    "api_run_71e00acdec7c445fbee437ed68795f29"
)


def test_run_history_query_endpoint():

    print("=" * 70)
    print("PHASE 9 - RUN HISTORY QUERY API")
    print("=" * 70)

    client = TestClient(app)

    # ==========================================
    # TEST 1 - DEFAULT HISTORY QUERY
    # ==========================================

    response = client.get(ENDPOINT)

    assert response.status_code == 200, response.text

    history = response.json()

    assert history["total_runs"] == 4
    assert history["filtered_total"] == 4
    assert len(history["runs"]) == 4

    print("Default history -> HTTP 200: PASS")

    # ==========================================
    # TEST 2 - HISTORY SUMMARIES
    # ==========================================

    assert history["status_counts"]["COMPLETED"] == 4

    assert history["scenario_counts"]["baseline"] == 4

    print("Status and scenario summaries: PASS")

    # ==========================================
    # TEST 3 - DEFAULT SORTING
    # ==========================================

    assert history["runs"][0]["run_id"] == KNOWN_RUN

    assert history["sort"] == {
        "by": "started_at",
        "order": "desc",
    }

    print("Newest-first sorting: PASS")

    # ==========================================
    # TEST 4 - STATUS FILTER
    # ==========================================

    response = client.get(
        ENDPOINT,
        params={"status": "COMPLETED"},
    )

    assert response.status_code == 200

    assert all(
        run["status"] == "COMPLETED"
        for run in response.json()["runs"]
    )

    print("Execution-status filtering: PASS")

    # ==========================================
    # TEST 5 - SCENARIO FILTER
    # ==========================================

    response = client.get(
        ENDPOINT,
        params={"scenario": "baseline"},
    )

    assert response.status_code == 200

    assert response.json()["filtered_total"] == 4

    print("Scenario filtering: PASS")

    # ==========================================
    # TEST 6 - EMPTY FILTER RESULT
    # ==========================================

    response = client.get(
        ENDPOINT,
        params={"scenario": "festive_peak"},
    )

    assert response.status_code == 200

    assert response.json()["filtered_total"] == 0
    assert response.json()["runs"] == []

    print("Empty scenario filter: PASS")

    # ==========================================
    # TEST 7 - PAGINATION
    # ==========================================

    first = client.get(
        ENDPOINT,
        params={"page": 1, "page_size": 2},
    )

    second = client.get(
        ENDPOINT,
        params={"page": 2, "page_size": 2},
    )

    assert first.status_code == 200
    assert second.status_code == 200

    first_data = first.json()
    second_data = second.json()

    assert len(first_data["runs"]) == 2
    assert len(second_data["runs"]) == 2

    assert first_data["pagination"]["total_pages"] == 2

    assert first_data["pagination"]["has_next"] is True
    assert second_data["pagination"]["has_previous"] is True

    first_ids = {
        item["run_id"]
        for item in first_data["runs"]
    }

    second_ids = {
        item["run_id"]
        for item in second_data["runs"]
    }

    assert first_ids.isdisjoint(second_ids)

    print("Multi-page history retrieval: PASS")

    # ==========================================
    # TEST 8 - ASCENDING SORTING
    # ==========================================

    response = client.get(
        ENDPOINT,
        params={
            "sort_by": "started_at",
            "order": "asc",
        },
    )

    assert response.status_code == 200

    assert response.json()["runs"][0]["run_id"] == (
        LEGACY_RUN
    )

    print("Oldest-first sorting: PASS")

    # ==========================================
    # TEST 9 - DURATION METADATA
    # ==========================================

    response = client.get(
        ENDPOINT,
        params={
            "sort_by": "duration_seconds",
            "order": "desc",
        },
    )

    assert response.status_code == 200

    durations = [
        run["duration_seconds"]
        for run in response.json()["runs"]
    ]

    assert durations == sorted(
        durations,
        reverse=True,
    )

    print("Execution-duration sorting: PASS")

    # ==========================================
    # TEST 10 - NAVIGATION LINKS
    # ==========================================

    known = next(
        run
        for run in history["runs"]
        if run["run_id"] == KNOWN_RUN
    )

    assert known["links"]["metrics"] == (
        f"/api/v1/runs/{KNOWN_RUN}/metrics"
    )

    assert known["links"]["validations"] == (
        f"/api/v1/runs/{KNOWN_RUN}/validations"
    )

    print("Run navigation links returned: PASS")

    # ==========================================
    # TEST 11 - INVALID QUERY PARAMETERS
    # ==========================================

    invalid_cases = [
        {"status": "UNKNOWN"},
        {"scenario": "unknown_scenario"},
        {"sort_by": "private_field"},
        {"order": "invalid"},
        {"page": 0},
        {"page": "invalid"},
        {"page_size": 0},
        {"page_size": 101},
    ]

    for params in invalid_cases:

        response = client.get(
            ENDPOINT,
            params=params,
        )

        assert response.status_code == 422, (
            params,
            response.text,
        )

    print("Invalid queries -> HTTP 422: PASS")

    # ==========================================
    # TEST 12 - SERVICE FAILURE
    # ==========================================

    with patch(
        "src.api.main.get_run_history_page",
        side_effect=RuntimeError(
            "PRIVATE_HISTORY_ERROR"
        ),
    ):

        response = client.get(ENDPOINT)

        assert response.status_code == 500

        assert "PRIVATE_HISTORY_ERROR" not in (
            response.text
        )

    print("Internal service failure -> HTTP 500: PASS")
    print("Private error details hidden: PASS")

    # ==========================================
    # TEST 13 - EXISTING HISTORY ENDPOINT
    # ==========================================

    original = client.get("/api/v1/runs")

    assert original.status_code == 200

    assert original.json()["total"] == 4
    assert len(original.json()["runs"]) == 4

    print("Original history API preserved: PASS")

    # ==========================================
    # TEST 14 - OPENAPI REGISTRATION
    # ==========================================

    schema = client.get("/openapi.json").json()

    assert "get" in schema["paths"][ENDPOINT]

    print("New history endpoint in OpenAPI: PASS")

    # ==========================================
    # TEST 15 - PUBLIC RESPONSE PRIVACY
    # ==========================================

    assert "generated_run_directory" not in (
        str(history)
    )

    assert "C:\\" not in str(history)

    print("Private filesystem paths hidden: PASS")

    # ==========================================
    # FINAL RESULTS
    # ==========================================

    print()
    print("=== RUN HISTORY API SUMMARY ===")
    print("Total runs:", history["total_runs"])
    print("Filtered runs:", history["filtered_total"])
    print("Status counts:", history["status_counts"])
    print("Scenario counts:", history["scenario_counts"])

    print()
    print("Generator execution performed: NO")
    print("Existing run records modified: NO")
    print("Original history API modified: NO")

    print()
    print("RUN HISTORY QUERY API TEST PASSED.")


if __name__ == "__main__":
    test_run_history_query_endpoint()
