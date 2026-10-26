
import json
import subprocess

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from src.config.simulation_config import load_simulation_config
from src.runtime.run_workspace import _reserve_in
from src.services.managed_execution import run_managed_simulation
from src.services.execution_lock import (
    SimulationBusyError,
    simulation_execution_slot,
)


# =====================================================
# FAKE GENERATOR - NEVER STARTS A REAL PROCESS
# =====================================================

class FakeProcess:

    def __init__(self, behavior):
        self.behavior = behavior
        self.pid = 123456
        self.stopped = False

    def poll(self):
        if self.behavior == "timeout":
            return -15 if self.stopped else None

        if self.behavior == "nonzero":
            return 7

        return 0

    def wait(self, timeout=None):
        if self.behavior == "timeout" and not self.stopped:
            raise subprocess.TimeoutExpired(
                cmd="mock_generator",
                timeout=timeout,
            )

        return self.poll()

    def terminate(self):
        self.stopped = True

    def kill(self):
        self.stopped = True


def test_managed_execution_failures():

    print("=" * 70)
    print("PHASE 9 - MANAGED EXECUTOR FAILURE INTEGRATION")
    print("=" * 70)

    config = load_simulation_config()

    with TemporaryDirectory(
        prefix="m14_managed_failure_"
    ) as temporary:

        fake_root = Path(temporary) / "d2c-api"
        runtime = fake_root / "runtime"
        runs_root = runtime / "runs"
        lock_path = runtime / "active_simulation.lock"

        runs_root.mkdir(parents=True)

        def reserve_fixture():
            return _reserve_in(
                runs_root,
                f"api_run_{uuid4().hex}",
            )

        def register_fake_process(process, workspace):
            metadata = Path(workspace) / "generator_process.json"

            metadata.write_text(
                json.dumps({
                    "process_id": process.pid,
                    "test_fixture": True,
                }),
                encoding="utf-8",
            )

            return metadata

        # Patch runtime locations so tests never
        # touch the actual Phase 9 execution records.

        with (
            patch(
                "src.services.execution_lock.ROOT",
                fake_root,
            ),
            patch(
                "src.services.execution_lock.LOCK_PATH",
                lock_path,
            ),
            patch(
                "src.services.managed_execution.RUNTIME_ROOT",
                runs_root,
            ),
            patch(
                "src.services.simulation_executor.RUNTIME_ROOT",
                runs_root,
            ),
            patch(
                "src.services.managed_execution.reserve_run_workspace",
                side_effect=reserve_fixture,
            ) as reserve_mock,
            patch(
                "src.services.managed_execution.register_generator_process",
                side_effect=register_fake_process,
            ),
            patch(
                "src.services.managed_execution.inspect_generator_process",
                return_value="NOT_RUNNING",
            ),
        ):

            def execute_fake(behavior):

                if behavior == "spawn_failure":
                    fake_result = OSError(
                        "Simulated launch failure"
                    )
                else:
                    fake_result = lambda *a, **kw: FakeProcess(
                        behavior
                    )

                with patch(
                    "src.services.managed_execution.subprocess.Popen",
                    side_effect=fake_result,
                ):
                    record, workspace = run_managed_simulation(
                        config
                    )

                status_path = (
                    workspace.working_directory
                    / "execution_status.json"
                )

                stored = json.loads(
                    status_path.read_text(encoding="utf-8")
                )

                assert stored == record
                assert not lock_path.exists()

                return record

            # -------------------------------------
            # TEST 1: NONZERO EXIT
            # -------------------------------------

            failed = execute_fake("nonzero")

            assert failed["status"] == "FAILED"
            assert failed["exit_code"] == 7

            print("Nonzero generator exit -> FAILED: PASS")

            # -------------------------------------
            # TEST 2: TIMEOUT
            # -------------------------------------

            timed_out = execute_fake("timeout")

            assert timed_out["status"] == "TIMED_OUT"
            assert timed_out["finished_at"] is not None

            print("Generator timeout -> TIMED_OUT: PASS")

            # -------------------------------------
            # TEST 3: MISSING OUTPUT
            # -------------------------------------

            missing = execute_fake("missing_output")

            assert missing["status"] == "FAILED"
            assert missing["exit_code"] == 0
            assert "Expected exactly one" in missing["error"]

            print("Missing generated datasets -> FAILED: PASS")

            # -------------------------------------
            # TEST 4: SUBPROCESS START FAILURE
            # -------------------------------------

            startup = execute_fake("spawn_failure")

            assert startup["status"] == "FAILED"
            assert "Simulated launch failure" in startup["error"]

            print("Subprocess launch error -> FAILED: PASS")

            # -------------------------------------
            # TEST 5: BUSY EXECUTION SLOT
            # -------------------------------------

            with simulation_execution_slot():

                before = reserve_mock.call_count

                try:
                    run_managed_simulation(config)

                except SimulationBusyError:
                    print(
                        "Concurrent simulation -> REJECTED (PASS)"
                    )

                else:
                    raise AssertionError(
                        "Concurrent simulation was accepted"
                    )

                assert reserve_mock.call_count == before

            assert not lock_path.exists()

            print("Lock released after handled failures: PASS")

            # -------------------------------------
            # TEST 6: UNCERTAIN TERMINATION
            # -------------------------------------

            try:
                with simulation_execution_slot(
                    can_release=lambda: False
                ):
                    pass

            except RuntimeError as exc:
                assert "lock retained" in str(exc)

            else:
                raise AssertionError(
                    "Unsafe lock release was allowed"
                )

            assert lock_path.is_file()

            print(
                "Unconfirmed termination retains lock: PASS"
            )

            # Remove only the mock lock in the
            # temporary test directory.
            lock_path.unlink()

    print("Temporary fixture cleanup: PASS")
    print("Actual generator execution: NO")
    print("Existing simulation records modified: NO")

    print()
    print("MANAGED EXECUTOR FAILURE INTEGRATION PASSED.")


if __name__ == "__main__":
    test_managed_execution_failures()
