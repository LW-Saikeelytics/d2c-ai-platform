
from src.services.dataset_download_service import (
    resolve_dataset_download,
)

from src.services.run_validation_service import (
    read_validation_manifest,
    structure_validation_evidence,
    ValidationEvidenceError,
)


# =====================================================
# PHASE 9.9.2B - CROSS-MANIFEST CONSISTENCY
# =====================================================

SOURCE_DATASETS = {
    "customers": "customer_count",
    "orders": "order_count",
    "events": "event_count",
    "daily_metrics": "daily_metrics_count",
    "behavior_history": "behavior_history_count",
    "conversion_history": "conversion_history_count",
}

ANALYTICS_TABLES = {
    "customer_analytics": "customer_analytics.csv",
    "product_analytics": "product_analytics.csv",
    "category_analytics": "category_analytics.csv",
    "business_kpi_summary": "business_kpi_summary.csv",
    "funnel_summary": "funnel_summary.csv",
    "daily_analytics": "daily_analytics.csv",
    "weekly_analytics": "weekly_analytics.csv",
    "monthly_analytics": "monthly_analytics.csv",
}


def valid_count(value):
    return type(value) is int and value >= 0


def compare_manifest_evidence(
    run_id,
    simulation,
    freeze,
    analytics,
    generated_run_name,
):

    if not all(
        isinstance(item, dict)
        for item in (simulation, freeze, analytics)
    ):
        raise ValidationEvidenceError(
            "Manifest evidence must contain objects"
        )

    # ==========================================
    # CHECK 1 - SIMULATION IDENTITY
    # ==========================================

    identity_valid = (
        simulation.get("run_id")
        == generated_run_name
        and isinstance(generated_run_name, str)
        and generated_run_name.startswith(
            "simulation_run_"
        )
    )

    # ==========================================
    # CHECK 2 - SOURCE RECORD COUNTS
    # ==========================================

    datasets = simulation.get("datasets")

    source_counts_valid = (
        isinstance(datasets, dict)
        and set(datasets) == set(SOURCE_DATASETS)
    )

    if source_counts_valid:

        for name, field in SOURCE_DATASETS.items():

            entry = datasets.get(name)
            count = freeze.get(field)

            if not (
                isinstance(entry, dict)
                and valid_count(count)
                and valid_count(entry.get("record_count"))
                and valid_count(simulation.get(field))
                and entry["record_count"] == count
                and simulation[field] == count
            ):
                source_counts_valid = False
                break

    # ==========================================
    # CHECK 3 - SIMULATION COUNTERS
    # ==========================================

    counters = simulation.get("counters")

    expected_counters = {
        "customer": freeze.get("customer_count"),
        "order": freeze.get("order_count"),
        "event": freeze.get("event_count"),
    }

    counters_valid = (
        isinstance(counters, dict)
        and set(counters) == set(expected_counters)
        and all(
            valid_count(value)
            and counters.get(name) == value
            for name, value in expected_counters.items()
        )
        and simulation.get("simulation_current_day")
        == freeze.get("simulation_days")
        and freeze.get("daily_metrics_count")
        == freeze.get("simulation_days")
    )

    # ==========================================
    # CHECK 4 - EXPORTED FILE REGISTRY
    # ==========================================

    expected_files = set()
    file_groups_valid = isinstance(datasets, dict)

    if file_groups_valid:

        for name in SOURCE_DATASETS:

            expected_pair = {
                f"{name}.csv",
                f"{name}.jsonl",
            }

            expected_files.update(expected_pair)

            entry = datasets.get(name, {})
            files = (
                entry.get("files")
                if isinstance(entry, dict)
                else None
            )

            if not (
                isinstance(files, list)
                and len(files) == 2
                and all(isinstance(f, str) for f in files)
                and set(files) == expected_pair
            ):
                file_groups_valid = False

    exported = simulation.get("exported_files")

    export_valid = (
        file_groups_valid
        and isinstance(exported, list)
        and all(isinstance(f, str) for f in exported)
        and len(exported) == len(expected_files)
        and set(exported) == expected_files
    )

    # ==========================================
    # CHECK 5 - ANALYTICS TABLE REGISTRY
    # ==========================================

    tables = analytics.get("tables")

    analytics_registry_valid = (
        isinstance(tables, dict)
        and analytics.get("table_count")
        == len(ANALYTICS_TABLES)
        and set(tables) == set(ANALYTICS_TABLES)
    )

    if analytics_registry_valid:

        for name, expected_file in ANALYTICS_TABLES.items():

            entry = tables[name]

            if not isinstance(entry, dict):
                analytics_registry_valid = False
                break

            columns = entry.get("columns")

            if not (
                entry.get("file") == expected_file
                and valid_count(entry.get("record_count"))
                and isinstance(columns, list)
                and bool(columns)
                and all(
                    isinstance(c, str) and bool(c)
                    for c in columns
                )
                and len(columns) == len(set(columns))
            ):
                analytics_registry_valid = False
                break

    # ==========================================
    # CHECK 6 - ANALYTICS RECORD COUNTS
    # ==========================================

    expected_analytics_counts = {
        "customer_analytics": freeze.get("customer_count"),
        "daily_analytics": freeze.get("daily_metrics_count"),
        "business_kpi_summary": 1,
        "funnel_summary": 1,
    }

    analytics_counts_valid = isinstance(tables, dict)

    if analytics_counts_valid:

        for name, expected in expected_analytics_counts.items():

            entry = tables.get(name)

            if not (
                valid_count(expected)
                and isinstance(entry, dict)
                and valid_count(entry.get("record_count"))
                and entry["record_count"] == expected
            ):
                analytics_counts_valid = False
                break

    # ==========================================
    # BUILD CONSISTENCY REPORT
    # ==========================================

    checks = {
        "simulation_identity": identity_valid,
        "source_record_counts": source_counts_valid,
        "simulation_counters": counters_valid,
        "exported_file_registry": export_valid,
        "analytics_table_registry": analytics_registry_valid,
        "analytics_record_counts": analytics_counts_valid,
    }

    passed = sum(checks.values())
    total = len(checks)

    return {
        "run_id": run_id,
        "evidence_type": "cross_manifest_comparison",
        "manifests_compared": [
            "simulation_manifest.json",
            "dataset_freeze_manifest.json",
            "analytics/analytics_manifest.json",
        ],
        "consistency_summary": {
            "total_checks": total,
            "passed": passed,
            "failed": total - passed,
            "all_passed": passed == total,
        },
        "checks": checks,
    }


# =====================================================
# LOAD THREE APPROVED MANIFESTS
# =====================================================

def get_validation_consistency(run_id):

    manifest_ids = {
        "simulation": "simulation_manifest.json",
        "freeze": "dataset_freeze_manifest.json",
        "analytics": "analytics__analytics_manifest.json",
    }

    manifests = {}
    generated_run_name = None

    for name, dataset_id in manifest_ids.items():

        dataset = resolve_dataset_download(
            run_id,
            dataset_id,
        )

        path = dataset["file_path"]

        if name == "simulation":
            generated_run_name = path.parent.name

        manifests[name] = read_validation_manifest(path)

    # Validate the Phase 6 freeze evidence contract
    # before comparing it with other manifests.

    structure_validation_evidence(
        run_id,
        manifests["freeze"],
    )

    return compare_manifest_evidence(
        run_id,
        manifests["simulation"],
        manifests["freeze"],
        manifests["analytics"],
        generated_run_name,
    )
