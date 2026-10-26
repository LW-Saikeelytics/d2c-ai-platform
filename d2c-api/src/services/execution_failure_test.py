
import json
import subprocess

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from src.config.simulation_config import (
    load_simulation_config,
)

from src.runtime.run_workspace import (
    RUNTIME_ROOT,
    _reserve_in,
)

from src.services.controlled_execution import (
    execute_simulation,
)

from src.services.run_history_service import (
    get_run_status,
    list_run_history,
)


def test_executor_failures():

    config = load_simulation_config()

    runtime_root = RUNTIME_ROOT.resolve()
    runtime_root.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(
        prefix="m14_executor_test_",
        dir=runtime_root,
    ) as temporary_directory:

        test_root = Path(temporary_directory).resolve()

        # Redirect all runtime checks to test fixtures.
        with (
            patch(
                "src.services.controlled_execution.RUNTIME_ROOT",
                test_root,
            ),
            patch(
                "src.services.simulation_executor.RUNTIME_ROOT",
                test_root,
            ),
            patch(
                "src.services.run_history_service.RUNTIME_ROOT",
                test_root,
            ),
        ):

            def new_workspace():
                return _reserve_in(
                    test_root,
                    f"api_run_{uuid4().hex}",
                )

            def execute_mocked(workspace, behavior):

                with patch(
                    "src.services.controlled_execution.subprocess.run",
                    side_effect=behavior,
                ):
                    record, log_path, status_path = (
                        execute_simulation(config, workspace)
                    )

                assert log_path.is_file()
                assert status_path.is_file()

                stored = get_run_status(workspace.run_id)

                assert stored == record
                assert stored["finished_at"] is not None

                return record, status_path

            def assert_running(command, **kwargs):

                status_file = (
                    Path(kwargs["cwd"])
                    / "execution_status.json"
                )

                running = json.loads(
                    status_file.read_text(encoding="utf-8")
                )

                assert running["status"] == "RUNNING"
                assert running["started_at"] is not None
                assert running["finished_at"] is None

                return command

            # ==========================================
            # TEST 1: NONZERO GENERATOR EXIT
            # ==========================================

            first = new_workspace()

            def nonzero_exit(command, **kwargs):
                assert_running(command, **kwargs)

                return subprocess.CompletedProcess(
                    command,
                    returncode=7,
                )

            failed, first_status = execute_mocked(
                first,
                nonzero_exit,
            )

            assert failed["status"] == "FAILED"
            assert failed["exit_code"] == 7
            assert "code 7" in failed["error"]

            print("Nonzero exit -> FAILED: PASS")
            print("Failure status persistence: PASS")

            # Ensure the same workspace cannot run twice.
            original_status = first_status.read_bytes()

            try:
                with patch(
                    "src.services.controlled_execution.subprocess.run",
                    side_effect=AssertionError(
                        "Duplicate subprocess invocation"
                    ),
                ):
                    execute_simulation(config, first)

            except FileExistsError:
                print(
                    "Duplicate execution: REJECTED (PASS)"
                )

            else:
                raise AssertionError(
                    "Duplicate execution was accepted"
                )

            assert first_status.read_bytes() == original_status

            print("Existing status preserved: PASS")

            # ==========================================
            # TEST 2: SUBPROCESS TIMEOUT
            # ==========================================

            second = new_workspace()

            def timeout_exit(command, **kwargs):
                assert_running(command, **kwargs)

                raise subprocess.TimeoutExpired(
                    cmd=command,
                    timeout=kwargs["timeout"],
                )

            timed_out, _ = execute_mocked(
                second,
                timeout_exit,
            )

            assert timed_out["status"] == "TIMED_OUT"
            assert timed_out["exit_code"] is None
            assert "exceeded" in timed_out["error"]

            print("Subprocess timeout -> TIMED_OUT: PASS")

            # ==========================================
            # TEST 3: MISSING GENERATED OUTPUT
            # ==========================================

            third = new_workspace()

            def missing_output(command, **kwargs):
                assert_running(command, **kwargs)

                return subprocess.CompletedProcess(
                    command,
                    returncode=0,
                )

            missing, _ = execute_mocked(
                third,
                missing_output,
            )

            assert missing["status"] == "FAILED"
            assert missing["exit_code"] == 0
            assert "Expected exactly one" in missing["error"]

            print("Missing output -> FAILED: PASS")

            # ==========================================
            # TEST 4: HISTORY COMPATIBILITY
            # ==========================================

            history = list_run_history()

            assert len(history) == 3

            states = {
                item["run_id"]: item["status"]
                for item in history
            }

            assert states[first.run_id] == "FAILED"
            assert states[second.run_id] == "TIMED_OUT"
            assert states[third.run_id] == "FAILED"

            print("Failure history retrieval: PASS")

    print("Temporary fixture cleanup: PASS")
    print("Actual generator execution performed: NO")
    print("Existing successful runs modified: NO")

    print()
    print("EXECUTOR FAILURE AND TIMEOUT TESTS PASSED.")


if __name__ == "__main__":

    print("=" * 70)
    print("PHASE 9 - EXECUTOR FAILURE AND TIMEOUT TESTS")
    print("=" * 70)

    test_executor_failures()