
from copy import deepcopy

from src.services.run_validation_service import (
    get_run_validation_results,
)

from src.services.validation_consistency_service import (
    get_validation_consistency,
)

from src.services.combined_validation_report_service import (
    CombinedValidationError,
    combine_validation_reports,
    get_combined_validation_report,
)


RUN_ID = (
    "api_run_ebaaf56bd9b14c1d9fca1af532387316"
)


def test_combined_validation_report():

    print("=" * 70)
    print("PHASE 9 - COMBINED VALIDATION REPORT")
    print("=" * 70)

    report = get_combined_validation_report(
        RUN_ID
    )

    assert report["run_id"] == RUN_ID

    print("Combined validation report loaded: PASS")

    # ==========================================
    # VERIFY RECORDED PHASE 6 VALIDATIONS
    # ==========================================

    recorded = report["recorded_validations"]

    assert recorded["summary"] == {
        "total_checks": 8,
        "passed": 8,
        "failed": 0,
        "all_passed": True,
    }

    assert len(recorded["checks"]) == 8

    print("Eight recorded generator checks: PASS")

    # ==========================================
    # VERIFY CROSS-MANIFEST COMPARISONS
    # ==========================================

    consistency = report["manifest_consistency"]

    assert consistency["summary"] == {
        "total_checks": 6,
        "passed": 6,
        "failed": 0,
        "all_passed": True,
    }

    assert len(consistency["checks"]) == 6

    print("Six cross-manifest checks: PASS")

    # ==========================================
    # VERIFY OVERALL SUMMARY
    # ==========================================

    assert report["overall_summary"] == {
        "total_checks": 14,
        "passed": 14,
        "failed": 0,
        "all_passed": True,
    }

    print("Combined 14-check summary: PASS")

    # ==========================================
    # VERIFY DATASET INFORMATION
    # ==========================================

    dataset = report["dataset"]

    assert dataset["status"] == "FROZEN"
    assert dataset["scenario"] == "baseline"
    assert dataset["simulation_days"] == 7
    assert dataset["record_counts"]["customers"] == 100
    assert dataset["record_counts"]["orders"] == 3
    assert dataset["record_counts"]["events"] == 87
    assert dataset["total_revenue"] == 35995.0

    print("Dataset metadata verified: PASS")

    # ==========================================
    # VERIFY EVIDENCE PROVENANCE
    # ==========================================

    assert recorded["evidence_type"] == (
        "recorded_generator_results"
    )

    assert consistency["evidence_type"] == (
        "cross_manifest_comparison"
    )

    assert report[
        "independent_phase6_revalidation"
    ] is False

    print("Validation evidence types distinguished: PASS")

    # ==========================================
    # VERIFY PUBLIC RESPONSE PRIVACY
    # ==========================================

    assert "C:\\" not in str(report)
    assert "file_path" not in str(report)
    assert "generated_run_directory" not in str(report)

    print("Private filesystem paths hidden: PASS")

    # ==========================================
    # PREPARE CONTROLLED TEST FIXTURES
    # ==========================================

    original_recorded = get_run_validation_results(
        RUN_ID
    )

    original_consistency = get_validation_consistency(
        RUN_ID
    )

    # ==========================================
    # TEST A RECORDED GENERATOR FAILURE
    # ==========================================

    failed_recorded = deepcopy(original_recorded)

    failed_recorded["checks"]["cross_table"] = False

    failed_recorded["validation_summary"] = {
        "total_checks": 8,
        "passed": 7,
        "failed": 1,
        "all_passed": False,
    }

    failed_report = combine_validation_reports(
        failed_recorded,
        deepcopy(original_consistency),
    )

    assert failed_report["overall_summary"] == {
        "total_checks": 14,
        "passed": 13,
        "failed": 1,
        "all_passed": False,
    }

    print("Recorded validation failure propagated: PASS")

    # ==========================================
    # TEST A CROSS-MANIFEST FAILURE
    # ==========================================

    failed_consistency = deepcopy(
        original_consistency
    )

    failed_consistency["checks"][
        "source_record_counts"
    ] = False

    failed_consistency["consistency_summary"] = {
        "total_checks": 6,
        "passed": 5,
        "failed": 1,
        "all_passed": False,
    }

    failed_report = combine_validation_reports(
        deepcopy(original_recorded),
        failed_consistency,
    )

    assert failed_report["overall_summary"] == {
        "total_checks": 14,
        "passed": 13,
        "failed": 1,
        "all_passed": False,
    }

    print("Manifest inconsistency propagated: PASS")

    # ==========================================
    # TEST MISMATCHED RUN IDENTIFIERS
    # ==========================================

    mismatched = deepcopy(original_consistency)

    mismatched["run_id"] = (
        "api_run_" + ("a" * 32)
    )

    try:
        combine_validation_reports(
            original_recorded,
            mismatched,
        )

    except CombinedValidationError:
        print("Mismatched run IDs rejected: PASS")

    else:
        raise AssertionError(
            "Mismatched run IDs accepted"
        )

    # ==========================================
    # TEST INCORRECT SUMMARY COUNTS
    # ==========================================

    incorrect = deepcopy(original_recorded)

    incorrect["validation_summary"]["passed"] = 99

    try:
        combine_validation_reports(
            incorrect,
            original_consistency,
        )

    except CombinedValidationError:
        print("Incorrect summary counts rejected: PASS")

    else:
        raise AssertionError(
            "Incorrect summary accepted"
        )

    # ==========================================
    # TEST NON-BOOLEAN CHECK RESULTS
    # ==========================================

    incorrect = deepcopy(original_recorded)

    incorrect["checks"]["dataset_quality"] = 1

    try:
        combine_validation_reports(
            incorrect,
            original_consistency,
        )

    except CombinedValidationError:
        print("Non-boolean check result rejected: PASS")

    else:
        raise AssertionError(
            "Invalid check result accepted"
        )

    # ==========================================
    # TEST INVALID RUN ID
    # ==========================================

    try:
        get_combined_validation_report(
            "invalid-run-id"
        )

    except ValueError:
        print("Invalid run ID rejected: PASS")

    else:
        raise AssertionError(
            "Invalid run ID accepted"
        )

    # ==========================================
    # FINAL SUMMARY
    # ==========================================

    summary = report["overall_summary"]

    print()
    print("=== COMBINED VALIDATION SUMMARY ===")
    print("Run ID:", RUN_ID)
    print("Recorded validations:", 8)
    print("Manifest consistency checks:", 6)
    print("Total checks:", summary["total_checks"])
    print("Passed:", summary["passed"])
    print("Failed:", summary["failed"])
    print("All passed:", summary["all_passed"])

    print()
    print("Independent Phase 6 revalidation: NO")
    print("Original manifests modified: NO")
    print("Generator execution performed: NO")
    print("Validation HTTP endpoint enabled: NO")

    print()
    print("COMBINED VALIDATION REPORT TEST PASSED.")


if __name__ == "__main__":
    test_combined_validation_report()
