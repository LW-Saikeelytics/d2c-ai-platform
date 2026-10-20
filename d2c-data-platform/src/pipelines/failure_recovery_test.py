
import io
import json
import subprocess
import tempfile

from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from . import pipeline_runner
from .pipeline_logger import PipelineLogger, ROOT


def read_logs(path):
    with path.open("r", encoding="utf-8") as file:
        return [
            json.loads(line)
            for line in file
            if line.strip()
        ]


def status_pairs(records):
    return [
        (record["stage"], record["status"])
        for record in records
    ]


def run_test():

    config = pipeline_runner.read_json(
        ROOT / "config" / "platform_config.json"
    )

    run_id = config["source"]["run_id"]

    # All simulated outputs and logs live
    # inside a disposable temporary directory.

    with tempfile.TemporaryDirectory(
        prefix="m14_pipeline_failure_test_"
    ) as folder:

        temp_root = Path(folder)
        log_path = temp_root / "test_logs.jsonl"

        manifests = {
            "mock_source": temp_root / "source.json",
            "mock_transform": temp_root / "transform.json",
            "mock_sink": temp_root / "sink.json",
            "integrity_audit": temp_root / "audit.json"
        }

        # Simulate one previously verified stage.

        manifests["mock_source"].write_text(
            json.dumps({"run_id": run_id}),
            encoding="utf-8"
        )

        # The fake execution plan deliberately
        # resembles the real dependency chain.

        definitions = [
            (
                "mock_source",
                "m14_test.source",
                [],
                "REUSE"
            ),
            (
                "mock_transform",
                "m14_test.transform",
                ["mock_source"],
                "BUILD"
            ),
            (
                "mock_sink",
                "m14_test.sink",
                ["mock_transform"],
                "BUILD"
            ),
            (
                "integrity_audit",
                "m14_test.audit",
                ["mock_sink"],
                "AUDIT"
            )
        ]

        plan = [
            {
                "name": name,
                "module": module,
                "dependencies": dependencies,
                "manifests": [manifests[name]],
                "action": action
            }
            for name, module, dependencies, action
            in definitions
        ]

        state = {
            "fail": True,
            "execution_id": "test-failure"
        }

        executed = []

        module_outputs = {
            "m14_test.transform": manifests["mock_transform"],
            "m14_test.sink": manifests["mock_sink"],
            "m14_test.audit": manifests["integrity_audit"]
        }

        # Replace actual subprocess execution with
        # a simulated stage running in memory.

        def simulated_subprocess(command, cwd, check):

            if Path(cwd) != ROOT or check is not True:
                raise AssertionError(
                    "Unexpected subprocess settings"
                )

            module = command[-1]
            executed.append(module)

            if (
                state["fail"]
                and module == "m14_test.transform"
            ):
                raise subprocess.CalledProcessError(
                    returncode=42,
                    cmd=command
                )

            if module not in module_outputs:
                raise AssertionError(
                    f"Unexpected test module: {module}"
                )

            output = {
                "run_id": run_id
            }

            if module == "m14_test.audit":
                output["status"] = "PASSED"

            module_outputs[module].write_text(
                json.dumps(output),
                encoding="utf-8"
            )

            return subprocess.CompletedProcess(
                command,
                returncode=0
            )

        # Send logs to the temporary test directory.

        def test_logger(
            source_run_id,
            execution_id=None
        ):
            return PipelineLogger(
                source_run_id=source_run_id,
                execution_id=state["execution_id"],
                log_path=log_path
            )

        with (
            patch.object(
                pipeline_runner,
                "build_execution_plan",
                return_value=plan
            ),
            patch.object(
                pipeline_runner,
                "PipelineLogger",
                side_effect=test_logger
            ),
            patch.object(
                pipeline_runner.subprocess,
                "run",
                side_effect=simulated_subprocess
            )
        ):

            # =====================================
            # TEST 1: INJECT A CONTROLLED FAILURE
            # =====================================

            failure_detected = False

            with redirect_stdout(io.StringIO()):

                try:
                    pipeline_runner.run_pipeline(
                        execute=True
                    )

                except subprocess.CalledProcessError as error:

                    if error.returncode == 42:
                        failure_detected = True

            if not failure_detected:
                raise AssertionError(
                    "Injected stage failure was not propagated"
                )

            failure_logs = read_logs(log_path)

            expected_failure = [
                ("mock_source", "STARTED"),
                ("mock_source", "REUSED"),
                ("mock_transform", "STARTED"),
                ("mock_transform", "FAILED")
            ]

            if status_pairs(failure_logs) != expected_failure:
                raise AssertionError(
                    "Failure log sequence is incorrect"
                )

            if (
                failure_logs[-1]["error_type"]
                != "CalledProcessError"
            ):
                raise AssertionError(
                    "Failure exception type was not logged"
                )

            if executed != ["m14_test.transform"]:
                raise AssertionError(
                    "Downstream execution was not stopped"
                )

            if (
                manifests["mock_sink"].exists()
                or manifests["integrity_audit"].exists()
            ):
                raise AssertionError(
                    "Downstream outputs were unexpectedly created"
                )

            print("Injected failure detected: PASS")
            print("FAILED stage recorded: PASS")
            print("Exception propagation: PASS")
            print("Downstream execution stopped: PASS")

            # =====================================
            # TEST 2: RECOVER AND RUN SUCCESSFULLY
            # =====================================

            state["fail"] = False
            state["execution_id"] = "test-recovery"
            executed.clear()

            with redirect_stdout(io.StringIO()):

                pipeline_runner.run_pipeline(
                    execute=True
                )

            all_logs = read_logs(log_path)

            recovery_logs = [
                record
                for record in all_logs
                if record["execution_id"]
                == "test-recovery"
            ]

            expected_recovery = [
                ("mock_source", "STARTED"),
                ("mock_source", "REUSED"),
                ("mock_transform", "STARTED"),
                ("mock_transform", "SUCCEEDED"),
                ("mock_sink", "STARTED"),
                ("mock_sink", "SUCCEEDED"),
                ("integrity_audit", "STARTED"),
                ("integrity_audit", "SUCCEEDED")
            ]

            if status_pairs(recovery_logs) != expected_recovery:
                raise AssertionError(
                    "Recovery log sequence is incorrect"
                )

            if executed != [
                "m14_test.transform",
                "m14_test.sink",
                "m14_test.audit"
            ]:
                raise AssertionError(
                    "Recovery stages were not executed correctly"
                )

            # All temporary output manifests should
            # now exist and pass the real validator.

            for name, path in manifests.items():
                pipeline_runner.check_manifests(
                    [path],
                    run_id
                )

            audit = pipeline_runner.read_json(
                manifests["integrity_audit"]
            )

            if audit.get("status") != "PASSED":
                raise AssertionError(
                    "Recovery audit did not pass"
                )

            # Check execution IDs and durations.

            if any(
                record["execution_id"] != "test-failure"
                for record in failure_logs
            ):
                raise AssertionError(
                    "Failure execution ID mismatch"
                )

            if any(
                record["duration_seconds"] is None
                for record in all_logs
                if record["status"] != "STARTED"
            ):
                raise AssertionError(
                    "Missing stage duration"
                )

            if len(all_logs) != 12:
                raise AssertionError(
                    "Expected 12 total test log records"
                )

            print("Recovery execution: PASS")
            print("Recovery audit: PASS")
            print("Manifest verification: PASS")
            print("Execution ID separation: PASS")
            print("Stage duration tracking: PASS")
            print("Temporary test isolation: PASS")

    print()
    print("PIPELINE FAILURE AND RECOVERY TEST PASSED.")


if __name__ == "__main__":

    print("=" * 70)
    print("PHASE 8 - PIPELINE FAILURE AND RECOVERY TEST")
    print("=" * 70)

    run_test()