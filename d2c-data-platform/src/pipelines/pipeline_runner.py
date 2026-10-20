import argparse
import json
import os
import subprocess
import sys
import time

from pathlib import Path
from .pipeline_logger import PipelineLogger

ROOT = Path(__file__).resolve().parents[2]

def read_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def build_steps(run_id):

    folder = f"run_id={run_id}"

    raw = ROOT / "data" / "raw" / folder
    processed = ROOT / "data" / "processed" / folder
    analytics = ROOT / "data" / "analytics" / folder
    parquet = ROOT / "data" / "parquet" / folder

    # name, Python module, dependencies, output manifests
    return [
        (
            "raw_ingestion",
            "src.layers.raw_layer",
            [],
            [raw / "_raw_manifest.json"]
        ),
        (
            "processed_transactions",
            "src.layers.processed_transactions",
            ["raw_ingestion"],
            [
                processed / "transactions"
                / "_processed_manifest.json"
            ]
        ),
        (
            "processed_entities",
            "src.layers.processed_entities",
            ["processed_transactions"],
            [
                processed / "entities"
                / "_processed_manifest.json"
            ]
        ),
        (
            "processed_activity",
            "src.layers.processed_activity",
            [
                "processed_transactions",
                "processed_entities"
            ],
            [
                processed / "activity"
                / "_processed_manifest.json"
            ]
        ),
        (
            "analytics_layer",
            "src.layers.analytics_layer",
            [
                "processed_entities",
                "processed_activity"
            ],
            [
                analytics / "business"
                / "_analytics_manifest.json"
            ]
        ),
        (
            "analytics_parquet",
            "src.storage.parquet_analytics",
            ["analytics_layer"],
            [
                parquet / "analytics" / "business"
                / "_parquet_manifest.json"
            ]
        ),
        (
            "events_parquet",
            "src.storage.partitioned_events",
            ["processed_transactions"],
            [
                parquet / "processed" / "events"
                / "_partition_manifest.json"
            ]
        ),
        (
            "transactions_parquet",
            "src.storage.partitioned_transactions",
            [
                "processed_transactions",
                "processed_entities",
                "processed_activity"
            ],
            [
                parquet / "processed" / "orders"
                / "_partition_manifest.json",
                parquet / "processed"
                / "behavior_history"
                / "_partition_manifest.json"
            ]
        ),
        (
            "core_parquet",
            "src.storage.remaining_processed_parquet",
            [
                "processed_entities",
                "processed_activity"
            ],
            [
                parquet / "processed" / "core"
                / "_parquet_manifest.json"
            ]
        ),
        (
            "integrity_audit",
            "src.storage.parquet_integrity_audit",
            [
                "analytics_parquet",
                "events_parquet",
                "transactions_parquet",
                "core_parquet"
            ],
            [
                ROOT / "reports"
                / "parquet_integrity_report.json"
            ]
        )
    ]


def check_manifests(paths, run_id):

    for path in paths:

        if not path.is_file():
            raise RuntimeError(
                f"Missing output manifest: {path}"
            )

        metadata = read_json(path)

        if metadata.get("run_id") != run_id:
            raise RuntimeError(
                f"Run ID mismatch: {path}"
            )


def determine_action(name, paths, run_id):

    # Always regenerate the final verification report.
    if name == "integrity_audit":
        return "AUDIT"

    existing = [path.is_file() for path in paths]

    if all(existing):
        check_manifests(paths, run_id)
        return "REUSE"

    if any(existing):
        raise RuntimeError(
            f"Partial output detected for {name}. "
            "Inspect it before rerunning."
        )

    # A directory with no manifest may contain
    # incomplete files from an interrupted run.
    for path in paths:
        if path.parent.exists():
            raise RuntimeError(
                f"Unverified output directory: "
                f"{path.parent}"
            )

    return "BUILD"


def build_execution_plan(run_id):

    steps = build_steps(run_id)

    planned = []
    actions = {}

    for name, module, dependencies, paths in steps:

        for dependency in dependencies:
            if dependency not in actions:
                raise RuntimeError(
                    f"Dependency ordering error: "
                    f"{name} -> {dependency}"
                )

        action = determine_action(
            name, paths, run_id
        )

        # Never silently reuse downstream output
        # if an upstream dependency must be rebuilt.
        if (
            action == "REUSE"
            and any(
                actions[dependency] == "BUILD"
                for dependency in dependencies
            )
        ):
            raise RuntimeError(
                f"{name} has existing output, but an "
                "upstream dependency needs rebuilding. "
                "Manual review is required."
            )

        actions[name] = action

        planned.append({
            "name": name,
            "module": module,
            "dependencies": dependencies,
            "manifests": paths,
            "action": action
        })

    return planned


def run_pipeline(execute=False):

    config = read_json(
        ROOT / "config" / "platform_config.json"
    )

    run_id = config["source"]["run_id"]

    print("=" * 70)
    print("PHASE 8 - AUTOMATED ETL/ELT PIPELINE")
    print("=" * 70)

    print(f"\nRun ID: {run_id}")
    print(
        f"Mode: {'EXECUTE' if execute else 'DRY RUN'}"
    )

    plan = build_execution_plan(run_id)

    print("\nEXECUTION PLAN:\n")

    for index, step in enumerate(plan, start=1):

        print(
            f"{index:02d}. "
            f"{step['name']:<26} "
            f"{step['action']}"
        )

    if not execute:

        print("\nExecution performed: NO")
        print("\nPIPELINE DRY RUN PASSED.")
        return

    # ==========================================
    # EXECUTE IN DEPENDENCY ORDER
    # ==========================================

    completed = set()

    for step in plan:

        name = step["name"]
        action = step["action"]

        if not set(
            step["dependencies"]
        ).issubset(completed):

            raise RuntimeError(
                f"Unmet dependency for {name}"
            )

        print("\n" + "-" * 70)
        print(f"Stage: {name}")
        print(f"Action: {action}")
        print("-" * 70, flush=True)

        if action == "REUSE":

            # Manifest verification only.
            # The final audit performs deeper checks.
            check_manifests(
                step["manifests"], run_id
            )

            print("Existing manifest verified.")

        else:

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    step["module"]
                ],
                cwd=ROOT,
                check=True
            )

            check_manifests(
                step["manifests"], run_id
            )

            if action == "AUDIT":

                report = read_json(
                    step["manifests"][0]
                )

                if report.get("status") != "PASSED":
                    raise RuntimeError(
                        "Final integrity audit failed."
                    )

        completed.add(name)

        print(f"Stage complete: {name}", flush=True)

    if len(completed) != len(plan):
        raise RuntimeError(
            "Not all pipeline stages completed."
        )

    print("\n" + "=" * 70)
    print(f"Pipeline steps completed: {len(completed)}")
    print("Final integrity audit: PASSED")
    print("\nAUTOMATED ETL/ELT PIPELINE PASSED.")


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--run",
        action="store_true",
        help="Execute the pipeline; default is dry run"
    )

    args = parser.parse_args()

    try:
        run_pipeline(execute=args.run)

    except (
        RuntimeError,
        ValueError,
        OSError,
        subprocess.CalledProcessError
    ) as error:

        print(f"\nPIPELINE FAILED: {error}")
        raise SystemExit(1)
