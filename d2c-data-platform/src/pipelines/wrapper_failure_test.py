
import io
import json
import subprocess
import sys
import tempfile

from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from . import run_with_logging
from .pipeline_logger import PipelineLogger, ROOT


def run_test():

    config_path = (
        ROOT / "config" / "platform_config.json"
    )

    with config_path.open(
        "r", encoding="utf-8"
    ) as file:
        run_id = json.load(file)["source"]["run_id"]

    scenarios = [
        {
            "id": "test-wrapper-failure",
            "outcome": "exit42",
            "return_code": 42,
            "status": "FAILED",
            "error_type": "PipelineExitCode42"
        },
        {
            "id": "test-wrapper-recovery",
            "outcome": "success",
            "return_code": 0,
            "status": "SUCCEEDED",
            "error_type": None
        },
        {
            "id": "test-wrapper-launch-error",
            "outcome": "os_error",
            "return_code": 1,
            "status": "FAILED",
            "error_type": "OSError"
        },
        {
            "id": "test-wrapper-interrupt",
            "outcome": "interrupt",
            "return_code": 130,
            "status": "FAILED",
            "error_type": "KeyboardInterrupt"
        }
    ]

    with tempfile.TemporaryDirectory(
        prefix="m14_wrapper_test_"
    ) as temp_dir:

        log_path = (
            Path(temp_dir) / "wrapper_logs.jsonl"
        )

        state = {}
        calls = []

        # Redirect all logger instances to
        # the disposable temporary log file.

        def create_test_logger(source_run_id):

            if source_run_id != run_id:
                raise AssertionError(
                    "Unexpected source run ID"
                )

            return PipelineLogger(
                source_run_id=source_run_id,
                execution_id=state["id"],
                log_path=log_path
            )

        # Simulate the child process.
        # The real ETL runner is never launched.

        def simulated_subprocess(
            command,
            check,
            env
        ):

            expected_command = [
                sys.executable,
                "-m",
                "src.pipelines.pipeline_runner",
                "--run"
            ]

            if command != expected_command:
                raise AssertionError(
                    "Unexpected runner command"
                )

            if check is not False:
                raise AssertionError(
                    "Unexpected subprocess check setting"
                )

            if (
                env.get("M14_PIPELINE_EXECUTION_ID")
                != state["id"]
            ):
                raise AssertionError(
                    "Execution ID was not forwarded"
                )

            calls.append(state["id"])

            outcome = state["outcome"]

            if outcome == "exit42":
                return subprocess.CompletedProcess(
                    command,
                    returncode=42
                )

            if outcome == "success":
                return subprocess.CompletedProcess(
                    command,
                    returncode=0
                )

            if outcome == "os_error":
                raise OSError(
                    "Simulated process launch failure"
                )

            if outcome == "interrupt":
                raise KeyboardInterrupt()

            raise AssertionError(
                "Unknown test scenario"
            )

        with (
            patch.object(
                run_with_logging,
                "PipelineLogger",
                side_effect=create_test_logger
            ),
            patch.object(
                run_with_logging.subprocess,
                "run",
                side_effect=simulated_subprocess
            ),
            patch.object(
                run_with_logging.sys,
                "argv",
                [
                    "run_with_logging.py",
                    "--run"
                ]
            )
        ):

            for scenario in scenarios:

                state.clear()
                state.update(scenario)

                with redirect_stdout(io.StringIO()):
                    return_code = (
                        run_with_logging.main()
                    )

                if (
                    return_code
                    != scenario["return_code"]
                ):
                    raise AssertionError(
                        f"Incorrect return code for "
                        f"{scenario['id']}: {return_code}"
                    )

        # ======================================
        # VALIDATE STRUCTURED WRAPPER LOGS
        # ======================================

        with log_path.open(
            "r",
            encoding="utf-8"
        ) as file:

            records = [
                json.loads(line)
                for line in file
                if line.strip()
            ]

        if len(records) != 8:
            raise AssertionError(
                f"Expected 8 log records, "
                f"found {len(records)}"
            )

        for scenario in scenarios:

            matching = [
                record
                for record in records
                if record["execution_id"]
                == scenario["id"]
            ]

            if len(matching) != 2:
                raise AssertionError(
                    "Expected STARTED and final status"
                )

            started, finished = matching

            if started["status"] != "STARTED":
                raise AssertionError(
                    "Missing STARTED event"
                )

            if (
                finished["status"]
                != scenario["status"]
            ):
                raise AssertionError(
                    "Incorrect final status"
                )

            if (
                finished["error_type"]
                != scenario["error_type"]
            ):
                raise AssertionError(
                    "Incorrect error metadata"
                )

            for record in matching:

                if record["stage"] != "pipeline_execution":
                    raise AssertionError(
                        "Incorrect stage name"
                    )

                if record["source_run_id"] != run_id:
                    raise AssertionError(
                        "Incorrect run ID in logs"
                    )

                if not record["timestamp_utc"].endswith(
                    "+00:00"
                ):
                    raise AssertionError(
                        "Timestamp must be UTC"
                    )

            duration = finished["duration_seconds"]

            if duration is None or duration < 0:
                raise AssertionError(
                    "Invalid execution duration"
                )

        expected_calls = [
            scenario["id"]
            for scenario in scenarios
        ]

        if calls != expected_calls:
            raise AssertionError(
                "Subprocess invocation sequence mismatch"
            )

        print("Non-zero exit detected: PASS")
        print("Overall FAILED status recorded: PASS")
        print("Failure exit code propagated: PASS")
        print("Successful recovery recorded: PASS")
        print("Process launch error handled: PASS")
        print("Keyboard interrupt handled: PASS")
        print("Execution ID forwarded: PASS")
        print("Execution IDs separated: PASS")
        print("Duration and error metadata: PASS")
        print("Temporary log isolation: PASS")

    print()
    print(
        "PIPELINE WRAPPER FAILURE TEST PASSED."
    )


if __name__ == "__main__":

    print("=" * 70)
    print("PHASE 8 - WRAPPER FAILURE REPORTING TEST")
    print("=" * 70)

    run_test()