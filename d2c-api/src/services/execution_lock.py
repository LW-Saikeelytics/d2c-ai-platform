
import json
import os
import subprocess
import sys

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from src.config.simulation_config import ROOT


# =====================================================
# PHASE 9.5.2 - CONCURRENT RUN PROTECTION
# =====================================================

LOCK_PATH = (
    ROOT / "runtime" / "active_simulation.lock"
)


class SimulationBusyError(RuntimeError):
    """Another simulation currently holds the execution lock."""


def utc_now():
    return datetime.now(timezone.utc).isoformat()


# =====================================================
# EXCLUSIVE EXECUTION SLOT
# =====================================================

@contextmanager
def simulation_execution_slot(*, can_release=None):

    runtime_dir = LOCK_PATH.parent

    runtime_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    if (
        runtime_dir.is_symlink()
        or runtime_dir.resolve() != (
            ROOT.resolve() / "runtime"
        )
    ):
        raise RuntimeError(
            "Unsafe execution lock directory"
        )

    owner_token = uuid4().hex

    metadata = {
        "owner_token": owner_token,
        "process_id": os.getpid(),
        "acquired_at": utc_now(),
    }

    # O_EXCL ensures that only one process can
    # create the lock file successfully.

    try:
        descriptor = os.open(
            str(LOCK_PATH),
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )

    except FileExistsError:
        raise SimulationBusyError(
            "Another simulation is already active"
        ) from None

    # Save lock ownership metadata.
    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(metadata, file, indent=2)
            file.flush()
            os.fsync(file.fileno())

    except BaseException:
        LOCK_PATH.unlink(missing_ok=True)
        raise

    try:
        yield LOCK_PATH

    finally:

        # Never release another owner's lock.

        if can_release is not None and not can_release():
            raise RuntimeError(
                "Generator termination not confirmed; "
                "execution lock retained for investigation"
            )

        current = json.loads(
            LOCK_PATH.read_text(encoding="utf-8")
        )

        if current.get("owner_token") != owner_token:
            raise RuntimeError(
                "Execution lock ownership mismatch"
            )

        LOCK_PATH.unlink()


# =====================================================
# SELF-TEST: NO GENERATOR EXECUTION
# =====================================================

def test_concurrent_execution():

    print("=" * 70)
    print("PHASE 9 - CONCURRENT EXECUTION PROTECTION")
    print("=" * 70)

    # =============================================
    # TEST 1 - ACQUIRE FIRST EXECUTION SLOT
    # =============================================

    with simulation_execution_slot():

        assert LOCK_PATH.is_file()

        print("First execution lock acquired: PASS")

        # =========================================
        # TEST 2 - REJECT DUPLICATE ACQUISITION
        # =========================================

        try:
            with simulation_execution_slot():
                raise AssertionError(
                    "Duplicate lock unexpectedly acquired"
                )

        except SimulationBusyError:
            print(
                "Concurrent execution: REJECTED (PASS)"
            )

        else:
            raise AssertionError(
                "Concurrent execution was accepted"
            )

        # =========================================
        # TEST 3 - CROSS-PROCESS COMPATIBILITY
        # =========================================

        child_script = """
from src.services.execution_lock import (
    simulation_execution_slot,
    SimulationBusyError,
)

try:
    with simulation_execution_slot():
        raise AssertionError("Child acquired busy slot")

except SimulationBusyError:
    print("CHILD_PROCESS_REJECTED")

else:
    raise AssertionError("Busy lock was accepted")
"""

        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONNOUSERSITE"] = "1"

        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                child_script,
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        assert result.returncode == 0, (
            result.stderr or result.stdout
        )

        assert (
            "CHILD_PROCESS_REJECTED"
            in result.stdout
        )

        print("Cross-process lock enforcement: PASS")

    # =============================================
    # TEST 4 - RELEASE AFTER SUCCESS
    # =============================================

    assert not LOCK_PATH.exists()

    print("Lock released after success: PASS")

    # =============================================
    # TEST 5 - REACQUIRE AFTER RELEASE
    # =============================================

    with simulation_execution_slot():
        assert LOCK_PATH.is_file()

    print("Lock reacquisition after release: PASS")

    # =============================================
    # TEST 6 - RELEASE AFTER EXCEPTION
    # =============================================

    try:

        with simulation_execution_slot():

            assert LOCK_PATH.is_file()

            raise RuntimeError(
                "Simulated application failure"
            )

    except RuntimeError as exc:

        assert str(exc) == (
            "Simulated application failure"
        )

    assert not LOCK_PATH.exists()

    print("Lock released after application error: PASS")

    print()
    print("Actual generator execution performed: NO")
    print("Existing simulation records modified: NO")
    print()
    print("CONCURRENT EXECUTION PROTECTION PASSED.")


if __name__ == "__main__":
    test_concurrent_execution()