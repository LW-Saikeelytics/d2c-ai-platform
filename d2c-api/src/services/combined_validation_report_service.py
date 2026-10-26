
from src.services.run_validation_service import (
    EXPECTED_VALIDATIONS,
    get_run_validation_results,
)

from src.services.validation_consistency_service import (
    get_validation_consistency,
)


# =====================================================
# PHASE 9.9.2C - COMBINED VALIDATION REPORT
# =====================================================

CONSISTENCY_CHECKS = (
    "simulation_identity",
    "source_record_counts",
    "simulation_counters",
    "exported_file_registry",
    "analytics_table_registry",
    "analytics_record_counts",
)


class CombinedValidationError(RuntimeError):
    """Combined validation evidence is inconsistent."""


# =====================================================
# VERIFY AN INDIVIDUAL VALIDATION SUMMARY
# =====================================================

def verify_check_summary(
    checks,
    summary,
    expected_names,
):

    if (
        not isinstance(checks, dict)
        or set(checks) != set(expected_names)
        or not isinstance(summary, dict)
    ):
        raise CombinedValidationError(
            "Invalid validation report structure"
        )

    if any(
        type(value) is not bool
        for value in checks.values()
    ):
        raise CombinedValidationError(
            "Validation outcomes must be booleans"
        )

    total = len(checks)
    passed = sum(checks.values())

    expected = {
        "total_checks": total,
        "passed": passed,
        "failed": total - passed,
        "all_passed": passed == total,
    }

    if summary != expected:
        raise CombinedValidationError(
            "Validation summary does not match checks"
        )

    return expected


# =====================================================
# COMBINE GENERATOR AND MANIFEST EVIDENCE
# =====================================================

def combine_validation_reports(
    recorded,
    consistency,
):

    if not (
        isinstance(recorded, dict)
        and isinstance(consistency, dict)
    ):
        raise CombinedValidationError(
            "Validation reports must be objects"
        )

    run_id = recorded.get("run_id")

    if (
        not isinstance(run_id, str)
        or not run_id
        or run_id != consistency.get("run_id")
    ):
        raise CombinedValidationError(
            "Validation run identifiers do not match"
        )

    if recorded.get("evidence_type") != (
        "recorded_generator_results"
    ):
        raise CombinedValidationError(
            "Unexpected generator evidence type"
        )

    if consistency.get("evidence_type") != (
        "cross_manifest_comparison"
    ):
        raise CombinedValidationError(
            "Unexpected consistency evidence type"
        )

    recorded_summary = verify_check_summary(
        recorded.get("checks"),
        recorded.get("validation_summary"),
        EXPECTED_VALIDATIONS,
    )

    consistency_summary = verify_check_summary(
        consistency.get("checks"),
        consistency.get("consistency_summary"),
        CONSISTENCY_CHECKS,
    )

    total = (
        recorded_summary["total_checks"]
        + consistency_summary["total_checks"]
    )

    passed = (
        recorded_summary["passed"]
        + consistency_summary["passed"]
    )

    overall_summary = {
        "total_checks": total,
        "passed": passed,
        "failed": total - passed,
        "all_passed": passed == total,
    }

    return {
        "run_id": run_id,

        "overall_summary": overall_summary,

        "recorded_validations": {
            "evidence_type": recorded["evidence_type"],
            "evidence_source": recorded["evidence_source"],
            "summary": recorded_summary,
            "checks": recorded["checks"],
        },

        "manifest_consistency": {
            "evidence_type": consistency["evidence_type"],
            "manifests_compared": consistency[
                "manifests_compared"
            ],
            "summary": consistency_summary,
            "checks": consistency["checks"],
        },

        "dataset": {
            "status": recorded["dataset_status"],
            "scenario": recorded["scenario"],
            "simulation_days": recorded["simulation_days"],
            "record_counts": recorded["record_counts"],
            "total_revenue": recorded["total_revenue"],
        },

        "independent_phase6_revalidation": False,
    }


# =====================================================
# RETRIEVE COMPLETE VALIDATION REPORT
# =====================================================

def get_combined_validation_report(run_id):

    recorded = get_run_validation_results(
        run_id
    )

    consistency = get_validation_consistency(
        run_id
    )

    return combine_validation_reports(
        recorded,
        consistency,
    )
