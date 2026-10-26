
from copy import deepcopy
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app

from src.services.dataset_catalog_service import (
    DatasetNotReadyError,
)


# =====================================================
# PHASE 9.9.3 - VALIDATION RESULTS API TEST
# =====================================================

RUN_ID = (
    "api_run_ebaaf56bd9b14c1d9fca1af532387316"
)

BASE_URL = "/api/v1/runs"


def test_validation_endpoint():

    print("=" * 70)
    print("PHASE 9 - VALIDATION RESULTS API ENDPOINT")
    print("=" * 70)

    client = TestClient(app)

    endpoint = f"{BASE_URL}/{RUN_ID}/validations"

    # ==========================================
    # TEST 1 - COMPLETED SIMULATION
    # ==========================================

    response = client.get(endpoint)

    assert response.status_code == 200, response.text

    report = response.json()

    assert report["run_id"] == RUN_ID

    print("Completed run -> HTTP 200: PASS")

    # ==========================================
    # TEST 2 - COMBINED VALIDATION SUMMARY
    # ==========================================

    overall = report["overall_summary"]

    assert overall == {
        "total_checks": 14,
        "passed": 14,
        "failed": 0,
        "all_passed": True,
    }

    print("Combined 14-check summary: PASS")

    # ==========================================
    # TEST 3 - RECORDED GENERATOR VALIDATIONS
    # ==========================================

    recorded = report["recorded_validations"]

    assert recorded["summary"]["total_checks"] == 8
    assert recorded["summary"]["passed"] == 8
    assert recorded["summary"]["failed"] == 0

    assert len(recorded["checks"]) == 8
    assert all(recorded["checks"].values())

    assert recorded["evidence_type"] == (
        "recorded_generator_results"
    )

    print("Eight recorded generator validations: PASS")

    # ==========================================
    # TEST 4 - CROSS-MANIFEST CONSISTENCY
    # ==========================================

    consistency = report["manifest_consistency"]

    assert consistency["summary"]["total_checks"] == 6
    assert consistency["summary"]["passed"] == 6
    assert consistency["summary"]["failed"] == 0

    assert len(consistency["checks"]) == 6
    assert all(consistency["checks"].values())

    assert consistency["evidence_type"] == (
        "cross_manifest_comparison"
    )

    print("Six manifest consistency checks: PASS")

    # ==========================================
    # TEST 5 - DATASET METADATA
    # ==========================================

    dataset = report["dataset"]

    assert dataset["status"] == "FROZEN"
    assert dataset["scenario"] == "baseline"
    assert dataset["simulation_days"] == 7

    assert dataset["record_counts"]["customers"] == 100
    assert dataset["record_counts"]["orders"] == 3
    assert dataset["record_counts"]["events"] == 87

    assert dataset["total_revenue"] == 35995.0

    print("Dataset metadata returned: PASS")

    # ==========================================
    # TEST 6 - EVIDENCE PROVENANCE
    # ==========================================

    assert report[
        "independent_phase6_revalidation"
    ] is False

    print("Evidence provenance preserved: PASS")

    # ==========================================
    # TEST 7 - PRIVATE PATH PROTECTION
    # ==========================================

    response_text = response.text

    assert "C:\\" not in response_text
    assert "file_path" not in response_text
    assert "generated_run_directory" not in response_text

    print("Private filesystem paths hidden: PASS")

    # ==========================================
    # TEST 8 - INVALID RUN IDENTIFIER
    # ==========================================

    invalid = client.get(
        f"{BASE_URL}/invalid-run-id/validations"
    )

    assert invalid.status_code == 422

    print("Invalid run ID -> HTTP 422: PASS")

    # ==========================================
    # TEST 9 - UNKNOWN RUN
    # ==========================================

    unknown_id = "api_run_" + ("f" * 32)

    unknown = client.get(
        f"{BASE_URL}/{unknown_id}/validations"
    )

    assert unknown.status_code == 404

    print("Unknown run -> HTTP 404: PASS")

    # ==========================================
    # TEST 10 - INCOMPLETE SIMULATION
    # ==========================================

    with patch(
        "src.api.main.get_combined_validation_report",
        side_effect=DatasetNotReadyError(
            "Run still active"
        ),
    ):

        pending = client.get(endpoint)

        assert pending.status_code == 409

    print("Incomplete simulation -> HTTP 409: PASS")

    # ==========================================
    # TEST 11 - INTERNAL VALIDATION FAILURE
    # ==========================================

    with patch(
        "src.api.main.get_combined_validation_report",
        side_effect=RuntimeError(
            "PRIVATE_VALIDATION_ERROR"
        ),
    ):

        failed = client.get(endpoint)

        assert failed.status_code == 500

        assert "PRIVATE_VALIDATION_ERROR" not in (
            str(failed.json())
        )

    print("Internal validation error -> HTTP 500: PASS")
    print("Internal error details hidden: PASS")

    # ==========================================
    # TEST 12 - A RECORDED FAILED CHECK
    # ==========================================

    simulated_failure = deepcopy(report)

    simulated_failure["recorded_validations"][
        "checks"
    ]["cross_table"] = False

    simulated_failure["recorded_validations"][
        "summary"
    ] = {
        "total_checks": 8,
        "passed": 7,
        "failed": 1,
        "all_passed": False,
    }

    simulated_failure["overall_summary"] = {
        "total_checks": 14,
        "passed": 13,
        "failed": 1,
        "all_passed": False,
    }

    with patch(
        "src.api.main.get_combined_validation_report",
        return_value=simulated_failure,
    ):

        failed_check = client.get(endpoint)

        assert failed_check.status_code == 200

        payload = failed_check.json()

        assert payload["overall_summary"][
            "all_passed"
        ] is False

        assert payload["overall_summary"][
            "failed"
        ] == 1

    print("Recorded failed check preserved: PASS")

    # ==========================================
    # TEST 13 - OPENAPI REGISTRATION
    # ==========================================

    schema_response = client.get("/openapi.json")

    assert schema_response.status_code == 200

    schema = schema_response.json()

    path = "/api/v1/runs/{run_id}/validations"

    assert "get" in schema["paths"][path]

    print("Validation endpoint in OpenAPI: PASS")

    # ==========================================
    # FINAL SUMMARY
    # ==========================================

    print()
    print("=== VALIDATION API SUMMARY ===")
    print("Run ID:", RUN_ID)
    print("Total checks:", overall["total_checks"])
    print("Passed:", overall["passed"])
    print("Failed:", overall["failed"])
    print("All passed:", overall["all_passed"])

    print()
    print("Independent Phase 6 revalidation: NO")
    print("Original manifests modified: NO")
    print("Generator execution performed: NO")

    print()
    print("VALIDATION RESULTS API ENDPOINT TEST PASSED.")


if __name__ == "__main__":
    test_validation_endpoint()
