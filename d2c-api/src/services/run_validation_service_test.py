
import json

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.services.dataset_download_service import (
    resolve_dataset_download,
)

from src.services.run_validation_service import (
    EXPECTED_VALIDATIONS,
    ValidationEvidenceError,
    get_run_validation_results,
    read_validation_manifest,
    structure_validation_evidence,
)


RUN_ID = (
    "api_run_ebaaf56bd9b14c1d9fca1af532387316"
)


def test_run_validation_service():

    print("=" * 70)
    print("PHASE 9 - VALIDATION RESULTS SERVICE")
    print("=" * 70)

    # ==========================================
    # TEST 1 - REAL COMPLETED SIMULATION
    # ==========================================

    report = get_run_validation_results(RUN_ID)

    assert report["run_id"] == RUN_ID
    assert report["dataset_status"] == "FROZEN"

    print("Completed run validation evidence loaded: PASS")

    summary = report["validation_summary"]

    assert summary["total_checks"] == 8
    assert summary["passed"] == 8
    assert summary["failed"] == 0
    assert summary["all_passed"] is True

    print("Eight recorded validations passed: PASS")

    # ==========================================
    # TEST 2 - VALIDATION CHECK NAMES
    # ==========================================

    assert set(report["checks"]) == set(
        EXPECTED_VALIDATIONS
    )

    assert all(report["checks"].values())

    print("All eight validation flags verified: PASS")

    # ==========================================
    # TEST 3 - DATASET RECORD COUNTS
    # ==========================================

    counts = report["record_counts"]

    assert counts["customers"] == 100
    assert counts["orders"] == 3
    assert counts["events"] == 87
    assert counts["daily_metrics"] == 7
    assert counts["behavior_history"] == 84
    assert counts["conversion_history"] == 48
    assert counts["purchase_events"] == 3

    print("Recorded dataset counts verified: PASS")

    assert report["total_revenue"] == 35995.0
    assert report["simulation_days"] == 7
    assert report["scenario"] == "baseline"

    print("Scenario, duration and revenue verified: PASS")

    # ==========================================
    # TEST 4 - PUBLIC RESPONSE STRUCTURE
    # ==========================================

    assert "file_path" not in report
    assert "generated_run_directory" not in report

    assert "C:\\" not in str(report)

    print("Private filesystem paths hidden: PASS")

    # ==========================================
    # TEST 5 - INVALID RUN ID
    # ==========================================

    try:
        get_run_validation_results("invalid-run-id")

    except ValueError:
        print("Invalid run ID rejected: PASS")

    else:
        raise AssertionError(
            "Invalid run ID was accepted"
        )

    # ==========================================
    # TEST 6 - CONTROLLED MANIFEST FIXTURES
    # ==========================================

    dataset = resolve_dataset_download(
        RUN_ID,
        "dataset_freeze_manifest.json",
    )

    original = read_validation_manifest(
        dataset["file_path"]
    )

    # A recorded false validation is a valid
    # report outcome, not malformed evidence.

    failed_fixture = deepcopy(original)

    failed_fixture["validations"]["cross_table"] = False

    failed_report = structure_validation_evidence(
        RUN_ID,
        failed_fixture,
    )

    assert failed_report["validation_summary"] == {
        "total_checks": 8,
        "passed": 7,
        "failed": 1,
        "all_passed": False,
    }

    assert failed_report["checks"]["cross_table"] is False

    print("Recorded failed validation reported: PASS")

    # A string "true" is not a boolean.

    invalid_flag = deepcopy(original)

    invalid_flag["validations"]["cross_table"] = "true"

    try:
        structure_validation_evidence(
            RUN_ID,
            invalid_flag,
        )

    except ValidationEvidenceError:
        print("Non-boolean validation flag rejected: PASS")

    else:
        raise AssertionError(
            "Malformed validation flag accepted"
        )

    # Missing validation check must be rejected.

    missing_check = deepcopy(original)

    del missing_check["validations"]["cross_table"]

    try:
        structure_validation_evidence(
            RUN_ID,
            missing_check,
        )

    except ValidationEvidenceError:
        print("Missing validation check rejected: PASS")

    else:
        raise AssertionError(
            "Incomplete validation report accepted"
        )

    # Corrupted counts must be rejected.

    invalid_count = deepcopy(original)

    invalid_count["event_count"] = "87"

    try:
        structure_validation_evidence(
            RUN_ID,
            invalid_count,
        )

    except ValidationEvidenceError:
        print("Invalid dataset count rejected: PASS")

    else:
        raise AssertionError(
            "Invalid dataset count accepted"
        )

    # ==========================================
    # TEST 7 - MALFORMED JSON
    # ==========================================

    with TemporaryDirectory(
        prefix="m14_validation_test_"
    ) as temporary:

        path = Path(temporary) / "invalid.json"

        path.write_text(
            "{invalid json",
            encoding="utf-8",
        )

        try:
            read_validation_manifest(path)

        except ValidationEvidenceError:
            print("Malformed validation JSON rejected: PASS")

        else:
            raise AssertionError(
                "Malformed validation JSON accepted"
            )

    # ==========================================
    # FINAL SUMMARY
    # ==========================================

    print()
    print("=== VALIDATION RESULTS SUMMARY ===")
    print("Run ID:", RUN_ID)
    print("Dataset status:", report["dataset_status"])
    print("Checks recorded:", summary["total_checks"])
    print("Passed:", summary["passed"])
    print("Failed:", summary["failed"])
    print("All passed:", summary["all_passed"])

    print()
    print("Independent revalidation performed: NO")
    print("Existing manifest files modified: NO")
    print("Generator execution performed: NO")
    print("Validation API endpoint enabled: NO")

    print()
    print("VALIDATION RESULTS SERVICE TEST PASSED.")


if __name__ == "__main__":
    test_run_validation_service()
