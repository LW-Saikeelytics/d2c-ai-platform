
import json
import os
import re

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import psutil

from src.services.execution_lock import LOCK_PATH
from src.services.interruption_recovery import (
    REVIEW_AFTER_MINUTES,
)


TOKEN_PATTERN = re.compile(r"[0-9a-f]{32}")


# =====================================================
# PHASE 9.5.3B - PROCESS OWNER VERIFICATION
# =====================================================

def check_owner_process(pid, acquired_at):

    try:
        process = psutil.Process(pid)

        created_at = datetime.fromtimestamp(
            process.create_time(),
            timezone.utc,
        )

        # Prevent confusing a recycled PID with
        # the process that originally acquired
        # the execution lock.

        if created_at > acquired_at + timedelta(seconds=2):
            return "PID_REUSED"

        if (
            not process.is_running()
            or process.status() == psutil.STATUS_ZOMBIE
        ):
            return "NOT_RUNNING"

        return "RUNNING"

    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return "NOT_RUNNING"

    except (psutil.AccessDenied, OSError, ValueError):
        return "UNKNOWN"


# =====================================================
# READ-ONLY EXECUTION LOCK ASSESSMENT
# =====================================================

def inspect_execution_lock(
    lock_path=LOCK_PATH,
    process_checker=check_owner_process,
    now=None,
):

    lock_path = Path(lock_path)
    now = now or datetime.now(timezone.utc)

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Inspection time must be timezone-aware")

    now = now.astimezone(timezone.utc)

    report = {
        "state": "ABSENT",
        "owner_pid": None,
        "age_seconds": None,
        "recovery_allowed": False,
    }

    if lock_path.is_symlink():
        report["state"] = "UNSAFE_LINK"
        return report

    if not lock_path.exists():
        return report

    if not lock_path.is_file():
        report["state"] = "INVALID_LOCK"
        return report

    try:
        if lock_path.stat().st_size > 131072:
            raise ValueError("Lock metadata too large")

        metadata = json.loads(
            lock_path.read_text(encoding="utf-8")
        )

        if not isinstance(metadata, dict):
            raise ValueError("Invalid lock metadata")

        token = metadata.get("owner_token")
        pid = metadata.get("process_id")
        acquired_text = metadata.get("acquired_at")

        if (
            not isinstance(token, str)
            or not TOKEN_PATTERN.fullmatch(token)
            or type(pid) is not int
            or pid <= 0
            or not isinstance(acquired_text, str)
        ):
            raise ValueError("Invalid lock ownership fields")

        acquired_at = datetime.fromisoformat(
            acquired_text
        )

        if (
            acquired_at.tzinfo is None
            or acquired_at.utcoffset() is None
        ):
            raise ValueError("Invalid lock timestamp")

        acquired_at = acquired_at.astimezone(
            timezone.utc
        )

        age = (now - acquired_at).total_seconds()

        if age < -30:
            raise ValueError("Lock timestamp is in the future")

    except (OSError, ValueError, TypeError):
        report["state"] = "INVALID_METADATA"
        return report

    report["owner_pid"] = pid
    report["age_seconds"] = int(age)

    process_state = process_checker(
        pid,
        acquired_at,
    )

    if process_state == "RUNNING":
        report["state"] = "OWNER_ACTIVE"

    elif process_state == "NOT_RUNNING":
        report["state"] = "OWNER_MISSING_REVIEW"

    elif process_state == "PID_REUSED":
        report["state"] = "PID_REUSED_REVIEW"

    else:
        report["state"] = "UNKNOWN_PROCESS_STATE"

    report["review_age_exceeded"] = (
        age >= REVIEW_AFTER_MINUTES * 60
    )

    # Important:
    # The existing lock metadata does not yet
    # record the generator child-process PID.
    #
    # Even a missing parent process does not
    # prove its generator child has stopped.
    #
    # Therefore automatic cleanup is forbidden.

    report["recovery_allowed"] = False

    return report


# =====================================================
# SAFE SELF-TEST
# =====================================================

def test_lock_recovery_guard():

    print("=" * 70)
    print("PHASE 9 - GUARDED LOCK RECOVERY INSPECTION")
    print("=" * 70)

    now = datetime.now(timezone.utc)

    with TemporaryDirectory(
        prefix="m14_lock_guard_test_"
    ) as directory:

        lock_path = Path(directory) / "test.lock"

        report = inspect_execution_lock(
            lock_path,
            now=now,
        )

        assert report["state"] == "ABSENT"

        print("Missing lock detection: PASS")

        metadata = {
            "owner_token": uuid4().hex,
            "process_id": os.getpid(),
            "acquired_at": (
                now - timedelta(minutes=30)
            ).isoformat(),
        }

        lock_path.write_text(
            json.dumps(metadata),
            encoding="utf-8",
        )

        original = lock_path.read_bytes()

        # Simulate an old lock whose owner
        # is still running.

        active = inspect_execution_lock(
            lock_path,
            process_checker=lambda pid, ts: "RUNNING",
            now=now,
        )

        assert active["state"] == "OWNER_ACTIVE"
        assert active["review_age_exceeded"]
        assert not active["recovery_allowed"]

        print("Old lock with active owner preserved: PASS")

        # Simulate a missing parent process.

        missing = inspect_execution_lock(
            lock_path,
            process_checker=lambda pid, ts: "NOT_RUNNING",
            now=now,
        )

        assert missing["state"] == "OWNER_MISSING_REVIEW"
        assert not missing["recovery_allowed"]

        print("Missing owner flagged for review: PASS")

        # Simulate process ID reuse.

        reused = inspect_execution_lock(
            lock_path,
            process_checker=lambda pid, ts: "PID_REUSED",
            now=now,
        )

        assert reused["state"] == "PID_REUSED_REVIEW"
        assert not reused["recovery_allowed"]

        print("Reused process ID detected: PASS")

        assert lock_path.read_bytes() == original

        print("Lock metadata unchanged: PASS")

        # Test a real process lookup using
        # this test program's own process ID.

        metadata["acquired_at"] = now.isoformat()

        lock_path.write_text(
            json.dumps(metadata),
            encoding="utf-8",
        )

        own_process = inspect_execution_lock(
            lock_path,
            now=now,
        )

        assert own_process["state"] == "OWNER_ACTIVE"

        print("Actual process-liveness check: PASS")

        # Invalid metadata must never authorize
        # cleanup.

        lock_path.write_text(
            "{invalid json",
            encoding="utf-8",
        )

        invalid = inspect_execution_lock(
            lock_path,
            now=now,
        )

        assert invalid["state"] == "INVALID_METADATA"
        assert not invalid["recovery_allowed"]

        print("Malformed lock metadata: REJECTED (PASS)")

    print("Temporary fixture cleanup: PASS")

    live_report = inspect_execution_lock()

    print()
    print("=== LIVE API EXECUTION LOCK ===")
    print("Lock state:", live_report["state"])
    print("Owner PID:", live_report["owner_pid"])
    print("Recovery allowed:", live_report["recovery_allowed"])

    print()
    print("Automatic lock deletion performed: NO")
    print("Existing run records modified: NO")
    print("Generator execution performed: NO")

    print()
    print("LOCK RECOVERY GUARD TEST PASSED.")


if __name__ == "__main__":
    test_lock_recovery_guard()