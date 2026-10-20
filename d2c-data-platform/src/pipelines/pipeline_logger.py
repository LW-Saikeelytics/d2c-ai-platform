
import json
import tempfile
import uuid

from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

VALID_STATUSES = {
    "STARTED",
    "SUCCEEDED",
    "FAILED",
    "REUSED",
    "SKIPPED"
}


class PipelineLogger:

    def __init__(
        self,
        source_run_id,
        log_path=None,
        execution_id=None
    ):

        if not source_run_id:
            raise ValueError("Source run ID is required")

        self.source_run_id = source_run_id

        self.execution_id = (
            execution_id or str(uuid.uuid4())
        )

        self.log_path = (
            Path(log_path)
            if log_path is not None
            else ROOT / "logs" / "pipeline_runs.jsonl"
        )

    # ==========================================
    # WRITE STRUCTURED LOG ENTRY
    # ==========================================

    def log(
        self,
        stage,
        status,
        duration_seconds=None,
        error_type=None
    ):

        if not stage:
            raise ValueError("Stage name is required")

        if status not in VALID_STATUSES:
            raise ValueError(
                f"Unsupported pipeline status: {status}"
            )

        if (
            duration_seconds is not None
            and (
                isinstance(duration_seconds, bool)
                or duration_seconds < 0
            )
        ):
            raise ValueError(
                "Duration must be non-negative"
            )

        record = {
            "timestamp_utc": datetime.now(
                timezone.utc
            ).isoformat(),

            "source_run_id": self.source_run_id,
            "execution_id": self.execution_id,
            "stage": stage,
            "status": status,

            "duration_seconds": (
                round(duration_seconds, 4)
                if duration_seconds is not None
                else None
            ),

            "error_type": error_type
        }

        self.log_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with self.log_path.open(
            "a",
            encoding="utf-8"
        ) as file:

            file.write(
                json.dumps(
                    record,
                    sort_keys=True,
                    ensure_ascii=False
                ) + "\n"
            )

        return record


# ==============================================
# LOGGER SELF-TEST
# ==============================================

def test_logger():

    config_path = (
        ROOT / "config" / "platform_config.json"
    )

    with config_path.open(
        "r", encoding="utf-8"
    ) as file:
        config = json.load(file)

    run_id = config["source"]["run_id"]

    # Test in an isolated temporary directory.
    # No real pipeline logs are modified.
    with tempfile.TemporaryDirectory() as temp_dir:

        log_path = (
            Path(temp_dir) / "test_pipeline.jsonl"
        )

        logger = PipelineLogger(
            source_run_id=run_id,
            log_path=log_path
        )

        logger.log(
            stage="test_stage",
            status="STARTED"
        )

        logger.log(
            stage="test_stage",
            status="SUCCEEDED",
            duration_seconds=1.25
        )

        logger.log(
            stage="simulated_failure",
            status="FAILED",
            duration_seconds=0.5,
            error_type="ValueError"
        )

        with log_path.open(
            "r", encoding="utf-8"
        ) as file:

            records = [
                json.loads(line)
                for line in file
                if line.strip()
            ]

        if len(records) != 3:
            raise AssertionError(
                "Expected exactly three log entries"
            )

        expected_statuses = [
            "STARTED",
            "SUCCEEDED",
            "FAILED"
        ]

        actual_statuses = [
            row["status"] for row in records
        ]

        if actual_statuses != expected_statuses:
            raise AssertionError(
                "Log statuses do not match"
            )

        if not all(
            row["source_run_id"] == run_id
            for row in records
        ):
            raise AssertionError(
                "Source run IDs do not match"
            )

        if len({
            row["execution_id"]
            for row in records
        }) != 1:
            raise AssertionError(
                "Execution IDs are inconsistent"
            )

        if records[1]["duration_seconds"] != 1.25:
            raise AssertionError(
                "Duration was not recorded correctly"
            )

        if records[2]["error_type"] != "ValueError":
            raise AssertionError(
                "Failure type was not recorded"
            )

        print("Structured JSONL entries: 3")
        print("STARTED event: PASS")
        print("SUCCEEDED event: PASS")
        print("FAILED event: PASS")
        print("Execution ID consistency: PASS")
        print("Duration tracking: PASS")
        print("Error type tracking: PASS")
        print("JSONL parsing: PASS")
        print("Test isolation: PASS")

    print("\nPIPELINE LOGGER TEST PASSED.")


if __name__ == "__main__":

    print("=" * 70)
    print("PHASE 8 - STRUCTURED PIPELINE LOGGER")
    print("=" * 70)

    test_logger()
