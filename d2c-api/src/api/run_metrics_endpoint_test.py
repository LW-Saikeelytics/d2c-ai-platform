
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app

from src.services.dataset_catalog_service import (
    DatasetNotReadyError,
)


# =====================================================
# PHASE 9.8.3 - BUSINESS METRICS API TEST
# =====================================================

RUN_ID = (
    "api_run_ebaaf56bd9b14c1d9fca1af532387316"
)

BASE_URL = "/api/v1/runs"


def test_run_metrics_endpoint():

    print("=" * 70)
    print("PHASE 9 - BUSINESS METRICS API ENDPOINT")
    print("=" * 70)

    client = TestClient(app)

    endpoint = f"{BASE_URL}/{RUN_ID}/metrics"

    # ==========================================
    # TEST 1 - COMPLETED SIMULATION
    # ==========================================

    response = client.get(endpoint)

    assert response.status_code == 200, response.text

    metrics = response.json()

    assert metrics["run_id"] == RUN_ID

    print("Completed run -> HTTP 200: PASS")

    # ==========================================
    # TEST 2 - RESPONSE STRUCTURE
    # ==========================================

    assert set(metrics.keys()) == {
        "run_id",
        "summary",
        "funnel",
        "trends",
    }

    print("Structured metrics response: PASS")

    # ==========================================
    # TEST 3 - BUSINESS KPIs
    # ==========================================

    summary = metrics["summary"]

    assert summary["customers"]["total_customers"] == 100
    assert summary["orders"]["total_orders"] == 3

    assert (
        summary["conversions"]["conversion_rate"]
        == 0.0625
    )

    assert (
        summary["revenue"]["total_revenue"]
        == 35995.0
    )

    print("Customer, order and revenue KPIs: PASS")

    # ==========================================
    # TEST 4 - SHOPPING FUNNEL
    # ==========================================

    funnel = metrics["funnel"]

    assert funnel["events"]["product_views"] == 48
    assert funnel["events"]["add_to_cart"] == 18
    assert funnel["events"]["purchases"] == 3

    print("Shopping funnel metrics: PASS")

    # ==========================================
    # TEST 5 - BUSINESS TRENDS
    # ==========================================

    trends = metrics["trends"]

    assert len(trends["daily"]) == 7
    assert len(trends["weekly"]) == 1
    assert len(trends["monthly"]) == 1

    print("Daily, weekly and monthly trends: PASS")

    # ==========================================
    # TEST 6 - RECONCILE METRICS
    # ==========================================

    daily = trends["daily"]

    assert sum(
        row["orders"] for row in daily
    ) == summary["orders"]["total_orders"]

    assert abs(
        sum(row["revenue"] for row in daily)
        - summary["revenue"]["total_revenue"]
    ) < 0.01

    print("Daily and summary totals reconciled: PASS")

    # ==========================================
    # TEST 7 - HIDE INTERNAL PATHS
    # ==========================================

    assert "file_path" not in str(metrics)
    assert "generated_run_directory" not in str(metrics)
    assert "C:\\" not in str(metrics)

    print("Internal filesystem paths hidden: PASS")

    # ==========================================
    # TEST 8 - INVALID RUN ID
    # ==========================================

    invalid = client.get(
        f"{BASE_URL}/invalid-run-id/metrics"
    )

    assert invalid.status_code == 422

    print("Invalid run ID -> HTTP 422: PASS")

    # ==========================================
    # TEST 9 - UNKNOWN RUN
    # ==========================================

    unknown_id = "api_run_" + ("f" * 32)

    unknown = client.get(
        f"{BASE_URL}/{unknown_id}/metrics"
    )

    assert unknown.status_code == 404

    print("Unknown run -> HTTP 404: PASS")

    # ==========================================
    # TEST 10 - INCOMPLETE SIMULATION
    # ==========================================

    with patch(
        "src.api.main.get_run_metrics",
        side_effect=DatasetNotReadyError(
            "Run still active"
        ),
    ):

        incomplete = client.get(endpoint)

        assert incomplete.status_code == 409

    print("Incomplete simulation -> HTTP 409: PASS")

    # ==========================================
    # TEST 11 - INTERNAL METRICS FAILURE
    # ==========================================

    with patch(
        "src.api.main.get_run_metrics",
        side_effect=RuntimeError(
            "PRIVATE_METRICS_ERROR"
        ),
    ):

        failed = client.get(endpoint)

        assert failed.status_code == 500

        assert "PRIVATE_METRICS_ERROR" not in (
            str(failed.json())
        )

    print("Internal metrics failure -> HTTP 500: PASS")
    print("Internal error details hidden: PASS")

    # ==========================================
    # TEST 12 - OPENAPI DOCUMENTATION
    # ==========================================

    schema_response = client.get("/openapi.json")

    assert schema_response.status_code == 200

    schema = schema_response.json()

    path = "/api/v1/runs/{run_id}/metrics"

    assert "get" in schema["paths"][path]

    print("Metrics endpoint registered in OpenAPI: PASS")

    # ==========================================
    # FINAL RESULTS
    # ==========================================

    print()
    print("=== METRICS API SUMMARY ===")
    print("Run ID:", RUN_ID)
    print(
        "Total customers:",
        summary["customers"]["total_customers"]
    )
    print(
        "Total orders:",
        summary["orders"]["total_orders"]
    )
    print(
        "Total revenue:",
        summary["revenue"]["total_revenue"]
    )
    print("Daily trend records:", len(daily))

    print()
    print("Generator execution performed: NO")
    print("Existing analytics files modified: NO")

    print()
    print("BUSINESS METRICS API ENDPOINT TEST PASSED.")


if __name__ == "__main__":
    test_run_metrics_endpoint()
