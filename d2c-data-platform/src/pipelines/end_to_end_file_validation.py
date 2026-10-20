
import json
import subprocess
import sys

from .pipeline_logger import ROOT
from .pipeline_runner import build_execution_plan
from .output_reproducibility import (
    OUTPUT_BASELINE,
    build_output_snapshot,
    verify_inputs
)


LOG_PATH = ROOT / "logs" / "pipeline_runs.jsonl"

AUDIT_PATH = (
    ROOT / "reports" / "parquet_integrity_report.json"
)


def read_json(path):

    if not path.is_file():
        raise RuntimeError(
            f"Required file missing: {path}"
        )

    with path.open(
        "r", encoding="utf-8"
    ) as file:
        return json.load(file)


def validate_execution_logs(
    records,
    run_id,
    plan
):

    if not records:
        raise RuntimeError(
            "No new pipeline log records"
        )

    execution_ids = {
        row["execution_id"]
        for row in records
    }

    if len(execution_ids) != 1:
        raise RuntimeError(
            "Execution IDs are inconsistent"
        )

    if any(
        row["source_run_id"] != run_id
        for row in records
    ):
        raise RuntimeError(
            "Unexpected source run ID in logs"
        )

    expected = [
        ("pipeline_execution", "STARTED")
    ]

    for step in plan:

        expected.append(
            (step["name"], "STARTED")
        )

        final_status = (
            "REUSED"
            if step["action"] == "REUSE"
            else "SUCCEEDED"
        )

        expected.append(
            (step["name"], final_status)
        )

    expected.append(
        ("pipeline_execution", "SUCCEEDED")
    )

    actual = [
        (row["stage"], row["status"])
        for row in records
    ]

    if actual != expected:
        raise RuntimeError(
            "Pipeline stage log sequence mismatch"
        )

    for record in records:

        if record["status"] == "STARTED":
            continue

        duration = record["duration_seconds"]

        if (
            duration is None
            or duration < 0
        ):
            raise RuntimeError(
                "Missing or invalid stage duration"
            )

        if record["error_type"] is not None:
            raise RuntimeError(
                "Unexpected stage error metadata"
            )

    return next(iter(execution_ids))


def main():

    print("=" * 70)
    print("PHASE 8 - END-TO-END FILE PIPELINE VALIDATION")
    print("=" * 70, flush=True)

    # =========================================
    # 1. VERIFY INPUTS
    # =========================================

    input_baseline = verify_inputs()

    run_id = input_baseline["run_id"]

    print("Frozen input baseline: PASS")
    print("Generator source hashes: PASS")

    # =========================================
    # 2. VERIFY EXISTING OUTPUTS
    # =========================================

    saved_outputs = read_json(
        OUTPUT_BASELINE
    )

    outputs_before = build_output_snapshot()

    if saved_outputs != outputs_before:
        raise RuntimeError(
            "Output baseline mismatch before execution"
        )

    print("Pre-execution output fingerprint: PASS")

    # =========================================
    # 3. PREPARE EXPECTED PIPELINE PLAN
    # =========================================

    plan = build_execution_plan(run_id)

    if len(plan) != 10:
        raise RuntimeError(
            f"Expected 10 stages, found {len(plan)}"
        )

    previous_log_size = (
        LOG_PATH.stat().st_size
        if LOG_PATH.is_file()
        else 0
    )

    # =========================================
    # 4. EXECUTE THE REAL LOGGED PIPELINE
    # =========================================

    print()
    print("EXECUTING REAL PIPELINE...", flush=True)
    print()

    subprocess.run(
        [
            sys.executable,
            "-m",
            "src.pipelines.run_with_logging",
            "--run"
        ],
        cwd=ROOT,
        check=True
    )

    print()
    print("END-TO-END VALIDATION SUMMARY")
    print("-" * 70)

    # =========================================
    # 5. VALIDATE PIPELINE LOGS
    # =========================================

    if not LOG_PATH.is_file():
        raise RuntimeError(
            "Pipeline execution log missing"
        )

    with LOG_PATH.open("rb") as file:

        file.seek(previous_log_size)

        new_records = [
            json.loads(line)
            for line in file.read().decode(
                "utf-8"
            ).splitlines()
            if line.strip()
        ]

    execution_id = validate_execution_logs(
        new_records,
        run_id,
        plan
    )

    print(
        f"Pipeline stages validated: {len(plan)}"
    )

    print(
        f"Execution log records: {len(new_records)}"
    )

    print("Execution log consistency: PASS")

    # =========================================
    # 6. VERIFY FINAL PARQUET AUDIT
    # =========================================

    audit = read_json(AUDIT_PATH)

    if audit.get("run_id") != run_id:
        raise RuntimeError(
            "Final audit run ID mismatch"
        )

    if audit.get("status") != "PASSED":
        raise RuntimeError(
            "Final Parquet integrity audit failed"
        )

    print("Parquet integrity audit: PASS")

    # =========================================
    # 7. RECHECK INPUTS AND OUTPUTS
    # =========================================

    inputs_after = verify_inputs()

    if inputs_after != input_baseline:
        raise RuntimeError(
            "Input fingerprint changed during execution"
        )

    outputs_after = build_output_snapshot()

    if outputs_after != outputs_before:
        raise RuntimeError(
            "Output files changed during execution"
        )

    if outputs_after != saved_outputs:
        raise RuntimeError(
            "Saved output baseline mismatch"
        )

    print("Post-execution input fingerprint: PASS")
    print("Post-execution output fingerprint: PASS")

    # =========================================
    # 8. FINAL RESULTS
    # =========================================

    print()
    print(f"Run ID: {run_id}")
    print(f"Execution ID: {execution_id}")

    print(
        "Tracked output files: "
        f"{outputs_after['total_file_count']}"
    )

    print(
        "Parquet files: "
        f"{outputs_after['parquet_file_count']}"
    )

    print(
        "Output fingerprint: "
        f"{outputs_after['output_fingerprint_sha256']}"
    )

    print()
    print(
        "END-TO-END FILE PIPELINE "
        "VALIDATION PASSED."
    )


if __name__ == "__main__":
    main()