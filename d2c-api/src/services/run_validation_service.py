
import json
import math

from pathlib import Path

from src.services.dataset_download_service import (
    resolve_dataset_download,
)


# =====================================================
# PHASE 9.9.2A - VALIDATION RESULTS SERVICE
# =====================================================

class ValidationEvidenceError(RuntimeError):
    """Persisted validation evidence is invalid."""


EXPECTED_VALIDATIONS = (
    "dataset_quality",
    "business_rules",
    "statistical_quality",
    "cross_table",
    "runtime_schema",
    "categorical_values",
    "daily_analytics",
    "analytics_dataset",
)


RECORD_COUNT_FIELDS = {
    "customers": "customer_count",
    "orders": "order_count",
    "events": "event_count",
    "behavior_history": "behavior_history_count",
    "conversion_history": "conversion_history_count",
    "daily_metrics": "daily_metrics_count",
    "purchase_events": "purchase_event_count",
}


# =====================================================
# READ MANIFEST WITH BASIC SAFETY VALIDATION
# =====================================================

def read_validation_manifest(file_path):

    file_path = Path(file_path)

    if file_path.is_symlink():
        raise ValidationEvidenceError(
            "Unsafe validation manifest"
        )

    try:

        if file_path.stat().st_size > 1048576:
            raise ValidationEvidenceError(
                "Validation manifest exceeds size limit"
            )

        manifest = json.loads(
            file_path.read_text(encoding="utf-8")
        )

    except (OSError, UnicodeError, ValueError) as exc:

        raise ValidationEvidenceError(
            "Unable to read validation manifest"
        ) from exc

    if not isinstance(manifest, dict):
        raise ValidationEvidenceError(
            "Validation manifest must be an object"
        )

    return manifest


# =====================================================
# VALIDATE AND STRUCTURE MANIFEST EVIDENCE
# =====================================================

def structure_validation_evidence(run_id, manifest):

    if manifest.get("dataset_status") != "FROZEN":
        raise ValidationEvidenceError(
            "Dataset freeze status is invalid"
        )

    validations = manifest.get("validations")

    if not isinstance(validations, dict):
        raise ValidationEvidenceError(
            "Validation results are missing"
        )

    if set(validations) != set(EXPECTED_VALIDATIONS):
        raise ValidationEvidenceError(
            "Validation check names do not match "
            "the expected Phase 6 contract"
        )

    checks = {}

    for name in EXPECTED_VALIDATIONS:

        value = validations[name]

        # Reject strings such as "true" and
        # integers such as 1.
        if type(value) is not bool:
            raise ValidationEvidenceError(
                f"Invalid validation result: {name}"
            )

        checks[name] = value

    # ==========================================
    # RECORDED DATASET COUNTS
    # ==========================================

    record_counts = {}

    for name, field in RECORD_COUNT_FIELDS.items():

        value = manifest.get(field)

        if type(value) is not int or value < 0:
            raise ValidationEvidenceError(
                f"Invalid dataset count: {field}"
            )

        record_counts[name] = value

    simulation_days = manifest.get("simulation_days")

    if (
        type(simulation_days) is not int
        or simulation_days <= 0
    ):
        raise ValidationEvidenceError(
            "Invalid simulation day count"
        )

    scenario = manifest.get("scenario")

    if not isinstance(scenario, str) or not scenario:
        raise ValidationEvidenceError(
            "Invalid simulation scenario"
        )

    revenue = manifest.get("total_revenue")

    if (
        type(revenue) not in (int, float)
        or not math.isfinite(revenue)
        or revenue < 0
    ):
        raise ValidationEvidenceError(
            "Invalid recorded revenue"
        )

    # ==========================================
    # BUILD VALIDATION SUMMARY
    # ==========================================

    passed = sum(checks.values())

    total = len(EXPECTED_VALIDATIONS)

    return {
        "run_id": run_id,
        "evidence_source": "dataset_freeze_manifest.json",
        "evidence_type": "recorded_generator_results",
        "dataset_status": "FROZEN",
        "scenario": scenario,
        "simulation_days": simulation_days,
        "validation_summary": {
            "total_checks": total,
            "passed": passed,
            "failed": total - passed,
            "all_passed": passed == total,
        },
        "checks": checks,
        "record_counts": record_counts,
        "total_revenue": float(revenue),
    }


# =====================================================
# RETRIEVE VALIDATION RESULTS FOR A COMPLETED RUN
# =====================================================

def get_run_validation_results(run_id):

    # Existing resolver verifies the run ID,
    # completed status, approved filename,
    # and dataset location.

    dataset = resolve_dataset_download(
        run_id,
        "dataset_freeze_manifest.json",
    )

    manifest = read_validation_manifest(
        dataset["file_path"]
    )

    return structure_validation_evidence(
        run_id,
        manifest,
    )
