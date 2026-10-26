
import json
import sys

from pathlib import Path

from src.runtime.run_workspace import (
    RUNTIME_ROOT,
    RUN_ID_PATTERN,
)


# =====================================================
# PHASE 9.7.2 - DATASET CATALOG SERVICE
# =====================================================

SOURCE_DATASETS = (
    "behavior_history.csv",
    "behavior_history.jsonl",
    "conversion_history.csv",
    "conversion_history.jsonl",
    "customers.csv",
    "customers.jsonl",
    "daily_metrics.csv",
    "daily_metrics.jsonl",
    "events.csv",
    "events.jsonl",
    "orders.csv",
    "orders.jsonl",
)

ANALYTICS_DATASETS = (
    "analytics/business_kpi_summary.csv",
    "analytics/category_analytics.csv",
    "analytics/customer_analytics.csv",
    "analytics/daily_analytics.csv",
    "analytics/funnel_summary.csv",
    "analytics/monthly_analytics.csv",
    "analytics/product_analytics.csv",
    "analytics/weekly_analytics.csv",
)

METADATA_DATASETS = (
    "dataset_freeze_manifest.json",
    "simulation_manifest.json",
    "simulation_scenario.json",
    "analytics/analytics_manifest.json",
)

DATASET_GROUPS = {
    "source": SOURCE_DATASETS,
    "analytics": ANALYTICS_DATASETS,
    "metadata": METADATA_DATASETS,
}

class DatasetNotReadyError(RuntimeError):
    """Requested simulation has not completed."""

def require_safe_directory(path):

    if path.is_symlink() or not path.is_dir():
        raise RuntimeError(
            "Expected a real dataset directory"
        )


# =====================================================
# LOCATE A COMPLETED RUN'S DATASET DIRECTORY
# =====================================================

def locate_dataset_root(
    run_id,
    runs_root=RUNTIME_ROOT,
):

    if (
        not isinstance(run_id, str)
        or not RUN_ID_PATTERN.fullmatch(run_id)
    ):
        raise ValueError("Invalid simulation run ID")

    runs_root = Path(runs_root)

    require_safe_directory(runs_root)

    workspace = runs_root / run_id

    if not workspace.exists():
        raise FileNotFoundError(
            "Simulation run not found"
        )

    require_safe_directory(workspace)

    status_path = workspace / "execution_status.json"

    if status_path.is_symlink():
        raise RuntimeError("Unsafe status file")

    if not status_path.is_file():
        raise RuntimeError("Run status is missing")

    if status_path.stat().st_size > 131072:
        raise RuntimeError("Run status file too large")

    status = json.loads(
        status_path.read_text(encoding="utf-8")
    )

    if (
        not isinstance(status, dict)
        or status.get("run_id") != run_id
    ):
        raise RuntimeError("Invalid run status")

    if status.get("status") != "COMPLETED":
        raise DatasetNotReadyError(
            "Datasets are available only for "
            "completed simulations"
        )

    data_directory = workspace / "data"
    generated_directory = data_directory / "generated"

    require_safe_directory(data_directory)
    require_safe_directory(generated_directory)

    generated_runs = [
        item
        for item in generated_directory.iterdir()
        if (
            item.name.startswith("simulation_run_")
            and item.is_dir()
            and not item.is_symlink()
        )
    ]

    if len(generated_runs) != 1:
        raise RuntimeError(
            "Expected exactly one generated dataset directory"
        )

    dataset_root = generated_runs[0]

    require_safe_directory(dataset_root)

    return dataset_root


# =====================================================
# BUILD A PUBLIC, READ-ONLY DATASET CATALOG
# =====================================================

def list_run_datasets(
    run_id,
    runs_root=RUNTIME_ROOT,
):

    dataset_root = locate_dataset_root(
        run_id,
        runs_root,
    )

    datasets = []
    missing = []

    for category, filenames in DATASET_GROUPS.items():

        for relative_name in filenames:

            file_path = (
                dataset_root / relative_name
            )

            if (
                file_path.is_symlink()
                or file_path.parent.is_symlink()
            ):
                raise RuntimeError(
                    "Unsafe dataset file detected"
                )

            if not file_path.is_file():
                missing.append(relative_name)
                continue

            # An API dataset ID contains no slashes.
            # Analytics filenames receive a prefix.
            dataset_id = relative_name.replace(
                "/", "__"
            )

            datasets.append({
                "dataset_id": dataset_id,
                "name": relative_name,
                "category": category,
                "format": file_path.suffix.lstrip("."),
                "size_bytes": file_path.stat().st_size,
            })

    # A COMPLETED run must contain every expected
    # file before we publish its catalog.

    if missing:
        raise RuntimeError(
            "Missing expected dataset files: "
            + ", ".join(missing)
        )

    return {
        "run_id": run_id,
        "dataset_count": len(datasets),
        "datasets": datasets,
    }


# =====================================================
# TEST THE REAL SWAGGER-GENERATED RUN
# =====================================================

def test_dataset_catalog(run_id):

    print("=" * 70)
    print("PHASE 9 - DATASET CATALOG SERVICE")
    print("=" * 70)

    catalog = list_run_datasets(run_id)

    datasets = catalog["datasets"]

    assert catalog["run_id"] == run_id

    print("Completed run located: PASS")

    assert catalog["dataset_count"] == 24

    print("Expected 24 dataset files discovered: PASS")

    for category, expected_count in (
        ("source", 12),
        ("analytics", 8),
        ("metadata", 4),
    ):

        count = sum(
            item["category"] == category
            for item in datasets
        )

        assert count == expected_count

        print(
            f"{category.title()} datasets: "
            f"{count} (PASS)"
        )

    identifiers = [
        item["dataset_id"]
        for item in datasets
    ]

    assert len(identifiers) == len(set(identifiers))

    print("Unique dataset identifiers: PASS")

    assert "customers.csv" in identifiers

    assert (
        "analytics__customer_analytics.csv"
        in identifiers
    )

    print("Dataset naming convention: PASS")

    assert all(
        item["size_bytes"] >= 0
        for item in datasets
    )

    print("File-size metadata available: PASS")

    assert all(
        not Path(item["name"]).is_absolute()
        and "\\" not in item["name"]
        for item in datasets
    )

    print("Absolute filesystem paths hidden: PASS")

    try:
        list_run_datasets("../unsafe")

    except ValueError:
        print("Unsafe run ID rejected: PASS")

    else:
        raise AssertionError(
            "Unsafe run ID unexpectedly accepted"
        )

    print()
    print("=== DATASET CATALOG SUMMARY ===")
    print("Run ID:", run_id)
    print("Total files:", catalog["dataset_count"])

    for extension in ("csv", "jsonl", "json"):

        count = sum(
            item["format"] == extension
            for item in datasets
        )

        print(f"{extension.upper()} files:", count)

    print()
    print("Files created or modified: NO")
    print("Generator execution performed: NO")
    print("Dataset downloads enabled: NO")

    print()
    print("DATASET CATALOG SERVICE TEST PASSED.")


if __name__ == "__main__":

    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python -m "
            "src.services.dataset_catalog_service "
            "<run_id>"
        )

    test_dataset_catalog(sys.argv[1])