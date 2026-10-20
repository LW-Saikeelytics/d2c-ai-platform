
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def build_pipeline_plan():

    config = load_json(
        ROOT / "config" / "platform_config.json"
    )

    run_id = config["source"]["run_id"]
    run_folder = f"run_id={run_id}"

    raw = ROOT / "data" / "raw" / run_folder

    processed = (
        ROOT / "data" / "processed" / run_folder
    )

    analytics = (
        ROOT / "data" / "analytics" / run_folder
    )

    parquet = (
        ROOT / "data" / "parquet" / run_folder
    )

    steps = [
        {
            "name": "raw_ingestion",
            "module": "src.layers.raw_layer",
            "depends_on": [],
            "manifests": [
                raw / "_raw_manifest.json"
            ]
        },
        {
            "name": "processed_transactions",
            "module": "src.layers.processed_transactions",
            "depends_on": ["raw_ingestion"],
            "manifests": [
                processed / "transactions"
                / "_processed_manifest.json"
            ]
        },
        {
            "name": "processed_entities",
            "module": "src.layers.processed_entities",
            "depends_on": ["processed_transactions"],
            "manifests": [
                processed / "entities"
                / "_processed_manifest.json"
            ]
        },
        {
            "name": "processed_activity",
            "module": "src.layers.processed_activity",
            "depends_on": [
                "processed_transactions",
                "processed_entities"
            ],
            "manifests": [
                processed / "activity"
                / "_processed_manifest.json"
            ]
        },
        {
            "name": "analytics_layer",
            "module": "src.layers.analytics_layer",
            "depends_on": [
                "processed_entities",
                "processed_activity"
            ],
            "manifests": [
                analytics / "business"
                / "_analytics_manifest.json"
            ]
        },
        {
            "name": "analytics_parquet",
            "module": "src.storage.parquet_analytics",
            "depends_on": ["analytics_layer"],
            "manifests": [
                parquet / "analytics" / "business"
                / "_parquet_manifest.json"
            ]
        },
        {
            "name": "events_parquet",
            "module": "src.storage.partitioned_events",
            "depends_on": ["processed_transactions"],
            "manifests": [
                parquet / "processed" / "events"
                / "_partition_manifest.json"
            ]
        },
        {
            "name": "transactions_parquet",
            "module": "src.storage.partitioned_transactions",
            "depends_on": [
                "processed_transactions",
                "processed_entities",
                "processed_activity"
            ],
            "manifests": [
                parquet / "processed" / "orders"
                / "_partition_manifest.json",

                parquet / "processed" / "behavior_history"
                / "_partition_manifest.json"
            ]
        },
        {
            "name": "core_parquet",
            "module": "src.storage.remaining_processed_parquet",
            "depends_on": [
                "processed_entities",
                "processed_activity"
            ],
            "manifests": [
                parquet / "processed" / "core"
                / "_parquet_manifest.json"
            ]
        },
        {
            "name": "integrity_audit",
            "module": "src.storage.parquet_integrity_audit",
            "depends_on": [
                "analytics_parquet",
                "events_parquet",
                "transactions_parquet",
                "core_parquet"
            ],
            "manifests": [
                ROOT / "reports"
                / "parquet_integrity_report.json"
            ]
        }
    ]

    # Validate dependency order and artifacts.
    statuses = {}
    problems = []
    manifest_count = 0

    print("=" * 70)
    print("PHASE 8 - ETL/ELT PIPELINE PREFLIGHT")
    print("=" * 70)

    print(f"\nRun ID: {run_id}")
    print("\nPIPELINE EXECUTION ORDER:\n")

    for index, step in enumerate(steps, start=1):

        name = step["name"]

        for dependency in step["depends_on"]:
            if dependency not in statuses:
                problems.append(
                    f"{name}: dependency not ordered: "
                    f"{dependency}"
                )

        paths = step["manifests"]

        present = [
            path for path in paths if path.is_file()
        ]

        manifest_count += len(present)

        if len(present) == len(paths):

            status = "PRESENT"

            for path in paths:

                try:
                    metadata = load_json(path)

                    if metadata.get("run_id") != run_id:
                        raise ValueError(
                            "Run ID mismatch"
                        )

                    if (
                        name == "integrity_audit"
                        and metadata.get("status") != "PASSED"
                    ):
                        raise ValueError(
                            "Integrity audit is not PASSED"
                        )

                except (ValueError, OSError) as error:
                    problems.append(
                        f"{name}: {path.name}: {error}"
                    )

        elif any(
            path.parent.exists() for path in paths
        ):

            status = "PARTIAL"

            problems.append(
                f"{name}: incomplete output manifests"
            )

        else:
            status = "NOT_BUILT"

        statuses[name] = status

        print(
            f"{index:02d}. "
            f"{name:<26} {status}"
        )

        print(f"    Module: {step['module']}")

    if problems:

        print("\nPREFLIGHT PROBLEMS:")

        for problem in problems:
            print("ERROR:", problem)

        raise SystemExit(
            "PIPELINE PREFLIGHT FAILED."
        )

    print("\n" + "=" * 70)

    print(f"Pipeline steps: {len(steps)}")
    print(f"Output manifests found: {manifest_count}")
    completed_steps = sum(
        status == "PRESENT"
        for status in statuses.values()
    )

    print(f"Steps with outputs: {completed_steps}")

    print("Execution performed: NO (read-only)")

    print("\nPIPELINE PREFLIGHT PASSED.")

    return steps


if __name__ == "__main__":
    build_pipeline_plan()