
import getpass
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .pipeline_logger import ROOT
from .pipeline_runner import build_execution_plan
from .output_reproducibility import (
    OUTPUT_BASELINE,
    build_output_snapshot,
    verify_inputs
)
from .end_to_end_file_validation import (
    validate_execution_logs
)


PSQL = Path(
    r"C:\Program Files\PostgreSQL\18\bin\psql.exe"
)

DATABASE_AUDIT = (
    ROOT / "sql" / "11_validate_database_integration.sql"
)

PARQUET_AUDIT = (
    ROOT / "reports" / "parquet_integrity_report.json"
)

LOG_PATH = ROOT / "logs" / "pipeline_runs.jsonl"

REPORT_PATH = (
    ROOT / "reports" / "full_platform_audit.json"
)


def read_json(path):

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def validate_file_platform():

    inputs = verify_inputs()
    outputs = build_output_snapshot()

    if outputs != read_json(OUTPUT_BASELINE):
        raise RuntimeError(
            "Saved output fingerprint does not match"
        )

    run_id = inputs["run_id"]

    if outputs["run_id"] != run_id:
        raise RuntimeError(
            "Input/output run ID mismatch"
        )

    audit = read_json(PARQUET_AUDIT)

    if (
        audit.get("run_id") != run_id
        or audit.get("status") != "PASSED"
    ):
        raise RuntimeError(
            "Parquet integrity report did not pass"
        )

    print("Frozen input baseline: PASS", flush=True)
    print("Generator source verification: PASS", flush=True)
    print("411-file output fingerprint: PASS", flush=True)
    print("Parquet integrity report: PASS", flush=True)

    return inputs, outputs


def validate_latest_execution(run_id):

    with LOG_PATH.open(
        "r", encoding="utf-8"
    ) as file:
        records = [
            json.loads(line)
            for line in file
            if line.strip()
        ]

    if not records:
        raise RuntimeError("No pipeline execution logs")

    execution_id = records[-1]["execution_id"]

    current_records = [
        record
        for record in records
        if record["execution_id"] == execution_id
    ]

    plan = build_execution_plan(run_id)

    if len(plan) != 10:
        raise RuntimeError(
            "Expected 10 pipeline stages"
        )

    validate_execution_logs(
        current_records,
        run_id,
        plan
    )

    if len(current_records) != 22:
        raise RuntimeError(
            "Expected 22 execution records"
        )

    print("Pipeline execution log validation: PASS", flush=True)
    print("Stage-level execution records: 22/22", flush=True)

    return execution_id


def validate_database():

    if not PSQL.is_file():
        raise RuntimeError(
            f"PostgreSQL executable not found: {PSQL}"
        )

    if not DATABASE_AUDIT.is_file():
        raise RuntimeError(
            "Database integration SQL file missing"
        )

    password = getpass.getpass(
        "Enter dreamnest_app password: "
    )

    # Password is passed only to the local
    # PostgreSQL client process. It is never
    # written to the audit report.

    environment = os.environ.copy()
    environment["PGPASSWORD"] = password

    del password

    print(
        "\nExecuting complete SQL integration audit...",
        flush=True
    )

    result = subprocess.run(
        [
            str(PSQL),
            "-X",
            "-U", "dreamnest_app",
            "-h", "localhost",
            "-p", "5432",
            "-d", "dreamnest_d2c",
            "-v", "ON_ERROR_STOP=1",
            "-f", str(DATABASE_AUDIT)
        ],
        cwd=ROOT,
        env=environment,
        check=False
    )

    environment.pop("PGPASSWORD", None)

    if result.returncode != 0:
        raise RuntimeError(
            "Database integration audit failed "
            f"with exit code {result.returncode}"
        )

    print("\nPostgreSQL staging audit: PASS", flush=True)
    print("SQL referential integrity: PASS", flush=True)
    print("Warehouse reconciliation: PASS", flush=True)
    print("Cross-layer financial reconciliation: PASS", flush=True)


def main():

    print("=" * 70, flush=True)
    print("PHASE 8 - FULL PLATFORM AUDIT", flush=True)
    print("=" * 70, flush=True)

    inputs_before, outputs_before = (
        validate_file_platform()
    )

    run_id = inputs_before["run_id"]

    execution_id = validate_latest_execution(
        run_id
    )

    validate_database()

    # Ensure the database audit did not
    # change tracked source or output files.

    inputs_after, outputs_after = (
        validate_file_platform()
    )

    if (
        inputs_after != inputs_before
        or outputs_after != outputs_before
    ):
        raise RuntimeError(
            "Platform fingerprints changed during audit"
        )

    report = {
        "version": 1,
        "audit_timestamp_utc":
            datetime.now(timezone.utc).isoformat(),
        "source_run_id": run_id,
        "last_pipeline_execution_id": execution_id,
        "input_fingerprint_sha256":
            inputs_after["fingerprint_sha256"],
        "output_fingerprint_sha256":
            outputs_after["output_fingerprint_sha256"],
        "tracked_output_files":
            outputs_after["total_file_count"],
        "parquet_files":
            outputs_after["parquet_file_count"],
        "pipeline_stages_validated": 10,
        "execution_records_validated": 22,
        "checks": {
            "input_baseline": "PASSED",
            "generator_source_hashes": "PASSED",
            "output_fingerprints": "PASSED",
            "parquet_integrity": "PASSED",
            "pipeline_execution_logs": "PASSED",
            "postgresql_staging": "PASSED",
            "referential_integrity": "PASSED",
            "warehouse_reconciliation": "PASSED",
            "cross_layer_reconciliation": "PASSED"
        },
        "validation_scope":
            "Existing outputs, latest successful "
            "pipeline execution, and database audit",
        "fresh_rebuild_tested": False,
        "overall_status": "PASSED"
    }

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with REPORT_PATH.open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(
            report,
            file,
            indent=2,
            sort_keys=True
        )

    print()
    print("=" * 70)
    print("FINAL PLATFORM AUDIT SUMMARY")
    print("=" * 70)

    print(f"Source run: {run_id}")
    print("Pipeline stages: 10/10")
    print("Execution log records: 22/22")
    print(
        f"Tracked outputs: "
        f"{outputs_after['total_file_count']}"
    )
    print(
        f"Parquet files: "
        f"{outputs_after['parquet_file_count']}"
    )
    print("Database integration: PASSED")
    print("Warehouse reconciliation: PASSED")
    print("Input/output fingerprints: MATCHED")
    print(f"Audit report: {REPORT_PATH}")

    print()
    print("FULL PLATFORM AUDIT PASSED.")


if __name__ == "__main__":
    main()