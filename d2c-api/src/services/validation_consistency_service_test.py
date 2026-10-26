
from copy import deepcopy

from src.services.dataset_download_service import (
    resolve_dataset_download,
)

from src.services.run_validation_service import (
    read_validation_manifest,
)

from src.services.validation_consistency_service import (
    compare_manifest_evidence,
    get_validation_consistency,
)


RUN_ID = (
    "api_run_ebaaf56bd9b14c1d9fca1af532387316"
)


def test_validation_consistency():

    print("=" * 70)
    print("PHASE 9 - CROSS-MANIFEST CONSISTENCY")
    print("=" * 70)

    report = get_validation_consistency(RUN_ID)

    summary = report["consistency_summary"]

    assert summary == {
        "total_checks": 6,
        "passed": 6,
        "failed": 0,
        "all_passed": True,
    }

    print("Three manifest files loaded: PASS")

    for check_name, result in report["checks"].items():
        assert result is True
        print(f"{check_name}: PASS")

    # ==========================================
    # LOAD FIXTURES WITHOUT MODIFYING ORIGINALS
    # ==========================================

    manifest_ids = {
        "simulation": "simulation_manifest.json",
        "freeze": "dataset_freeze_manifest.json",
        "analytics": "analytics__analytics_manifest.json",
    }

    originals = {}

    for name, dataset_id in manifest_ids.items():

        dataset = resolve_dataset_download(
            RUN_ID,
            dataset_id,
        )

        originals[name] = read_validation_manifest(
            dataset["file_path"]
        )

    generated_name = originals["simulation"]["run_id"]

    def check_modified_fixture(
        expected_failed_check,
        simulation=None,
        freeze=None,
        analytics=None,
        generated_run_name=None,
    ):

        result = compare_manifest_evidence(
            RUN_ID,
            simulation or deepcopy(originals["simulation"]),
            freeze or deepcopy(originals["freeze"]),
            analytics or deepcopy(originals["analytics"]),
            generated_run_name or generated_name,
        )

        assert result["checks"][expected_failed_check] is False
        assert not result["consistency_summary"]["all_passed"]

    # ==========================================
    # DETECT INCONSISTENT RECORD COUNTS
    # ==========================================

    bad_simulation = deepcopy(originals["simulation"])

    bad_simulation["datasets"]["orders"][
        "record_count"
    ] = 999

    check_modified_fixture(
        "source_record_counts",
        simulation=bad_simulation,
    )

    print("Mismatched source counts detected: PASS")

    # ==========================================
    # DETECT INCORRECT COUNTERS
    # ==========================================

    bad_simulation = deepcopy(originals["simulation"])

    bad_simulation["counters"]["event"] = 999

    check_modified_fixture(
        "simulation_counters",
        simulation=bad_simulation,
    )

    print("Mismatched counters detected: PASS")

    # ==========================================
    # DETECT INCOMPLETE EXPORTED FILE REGISTRY
    # ==========================================

    bad_simulation = deepcopy(originals["simulation"])

    bad_simulation["exported_files"].remove(
        "customers.csv"
    )

    check_modified_fixture(
        "exported_file_registry",
        simulation=bad_simulation,
    )

    print("Missing source export detected: PASS")

    # ==========================================
    # DETECT ANALYTICS COUNT MISMATCH
    # ==========================================

    bad_analytics = deepcopy(originals["analytics"])

    bad_analytics["tables"]["customer_analytics"][
        "record_count"
    ] = 99

    check_modified_fixture(
        "analytics_record_counts",
        analytics=bad_analytics,
    )

    print("Mismatched analytics counts detected: PASS")

    # ==========================================
    # DETECT INCORRECT ANALYTICS REGISTRY
    # ==========================================

    bad_analytics = deepcopy(originals["analytics"])

    bad_analytics["tables"]["daily_analytics"][
        "file"
    ] = "wrong_file.csv"

    check_modified_fixture(
        "analytics_table_registry",
        analytics=bad_analytics,
    )

    print("Invalid analytics registry detected: PASS")

    # ==========================================
    # DETECT SIMULATION IDENTITY MISMATCH
    # ==========================================

    check_modified_fixture(
        "simulation_identity",
        generated_run_name="simulation_run_other",
    )

    print("Simulation identity mismatch detected: PASS")

    # ==========================================
    # INVALID RUN ID
    # ==========================================

    try:
        get_validation_consistency("invalid-run-id")

    except ValueError:
        print("Invalid run ID rejected: PASS")

    else:
        raise AssertionError(
            "Invalid run ID was accepted"
        )

    print()
    print("=== CONSISTENCY SUMMARY ===")
    print("Run ID:", RUN_ID)
    print("Checks:", summary["total_checks"])
    print("Passed:", summary["passed"])
    print("Failed:", summary["failed"])

    print()
    print("Independent Phase 6 validation rerun: NO")
    print("Existing manifests modified: NO")
    print("Generator execution performed: NO")

    print()
    print("CROSS-MANIFEST CONSISTENCY TEST PASSED.")


if __name__ == "__main__":
    test_validation_consistency()