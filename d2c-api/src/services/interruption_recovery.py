
import json

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from src.runtime.run_workspace import (
    RUNTIME_ROOT,
    RUN_ID_PATTERN,
)

from src.services.execution_lock import LOCK_PATH


# =====================================================
# PHASE 9.5.3A - INTERRUPTED RUN INSPECTION
# =====================================================

REVIEW_AFTER_MINUTES = 15

ACTIVE_STATUSES = {
    "RESERVED",
    "RUNNING",
}


def parse_timestamp(value):

    if not isinstance(value, str):
        return None

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return None

    return parsed.astimezone(timezone.utc)


def read_metadata(path):

    if path.is_symlink():
        raise ValueError("Unsafe metadata symlink")

    if path.stat().st_size > 131072:
        raise ValueError("Metadata file too large")

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(data, dict):
        raise ValueError("Metadata must be an object")

    return data


# =====================================================
# INSPECT RUNS AND ACTIVE EXECUTION LOCK
# =====================================================

def inspect_interrupted_runs(
    runs_root=RUNTIME_ROOT,
    lock_path=LOCK_PATH,
    now=None,
):

    runs_root = Path(runs_root)
    lock_path = Path(lock_path)

    now = now or datetime.now(timezone.utc)

    if now.tzinfo is None:
        raise ValueError("Inspection time must have timezone")

    now = now.astimezone(timezone.utc)

    threshold = REVIEW_AFTER_MINUTES * 60

    report = {
        "runs_checked": 0,
        "candidates": [],
        "lock_state": "ABSENT",
    }

    if runs_root.is_symlink():
        raise RuntimeError("Unsafe runtime directory")

    if runs_root.is_dir():

        for workspace in runs_root.iterdir():

            if (
                workspace.is_symlink()
                or not workspace.is_dir()
                or not RUN_ID_PATTERN.fullmatch(
                    workspace.name
                )
            ):
                continue

            report["runs_checked"] += 1

            status_path = (
                workspace / "execution_status.json"
            )

            claim_path = (
                workspace / "execution.claim"
            )

            if not status_path.exists():

                if claim_path.is_file():

                    age = (
                        now.timestamp()
                        - claim_path.stat().st_mtime
                    )

                    if age >= threshold:
                        report["candidates"].append({
                            "run_id": workspace.name,
                            "reason": "CLAIM_WITHOUT_STATUS",
                        })

                continue

            try:
                record = read_metadata(status_path)

                if record.get("run_id") != workspace.name:
                    raise ValueError("Run ID mismatch")

            except (OSError, ValueError) as exc:

                report["candidates"].append({
                    "run_id": workspace.name,
                    "reason": "INVALID_STATUS",
                    "detail": str(exc),
                })

                continue

            status = record.get("status")

            if status not in ACTIVE_STATUSES:
                continue

            field = (
                "started_at"
                if status == "RUNNING"
                else "created_at"
            )

            timestamp = parse_timestamp(
                record.get(field)
            )

            if timestamp is None:

                report["candidates"].append({
                    "run_id": workspace.name,
                    "reason": "INVALID_ACTIVE_TIMESTAMP",
                    "status": status,
                })

                continue

            age = (
                now - timestamp
            ).total_seconds()

            if age >= threshold:

                report["candidates"].append({
                    "run_id": workspace.name,
                    "reason": "ACTIVE_RUN_REVIEW",
                    "status": status,
                    "age_seconds": int(age),
                })

    # -------------------------------------------------
    # INSPECT GLOBAL EXECUTION LOCK
    # -------------------------------------------------

    if lock_path.is_symlink():

        report["lock_state"] = "UNSAFE_LINK"

    elif lock_path.exists():

        try:
            metadata = read_metadata(lock_path)

            acquired = parse_timestamp(
                metadata.get("acquired_at")
            )

            if acquired is None:
                raise ValueError(
                    "Invalid lock acquisition timestamp"
                )

            age = (
                now - acquired
            ).total_seconds()

            report["lock_state"] = (
                "REVIEW_REQUIRED"
                if age >= threshold
                else "PRESENT"
            )

        except (OSError, ValueError):
            report["lock_state"] = "INVALID_METADATA"

    return report


# =====================================================
# SELF-TEST WITH TEMPORARY FIXTURES
# =====================================================

def test_interruption_inspection():

    print("=" * 70)
    print("PHASE 9 - INTERRUPTED RUN INSPECTION")
    print("=" * 70)

    now = datetime.now(timezone.utc)

    old = (
        now - timedelta(minutes=30)
    ).isoformat()

    recent = (
        now - timedelta(minutes=1)
    ).isoformat()

    with TemporaryDirectory(
        prefix="m14_recovery_test_"
    ) as temporary_dir:

        root = Path(temporary_dir)
        runs_root = root / "runs"
        runs_root.mkdir()

        lock_path = root / "active_simulation.lock"

        records = {}

        def create_fixture(status, timestamp):

            run_id = f"api_run_{uuid4().hex}"

            workspace = runs_root / run_id
            workspace.mkdir()

            record = {
                "run_id": run_id,
                "status": status,
                "created_at": timestamp,
                "started_at": (
                    timestamp
                    if status == "RUNNING"
                    else None
                ),
            }

            path = (
                workspace / "execution_status.json"
            )

            path.write_text(
                json.dumps(record),
                encoding="utf-8",
            )

            records[run_id] = {
                "status": status,
                "path": path,
            }

            return run_id

        old_running = create_fixture(
            "RUNNING", old
        )

        old_reserved = create_fixture(
            "RESERVED", old
        )

        recent_reserved = create_fixture(
            "RESERVED", recent
        )

        completed = create_fixture(
            "COMPLETED", old
        )

        lock_path.write_text(
            json.dumps({
                "owner_token": uuid4().hex,
                "process_id": 12345,
                "acquired_at": old,
            }),
            encoding="utf-8",
        )

        original_files = {
            item["path"]: item["path"].read_bytes()
            for item in records.values()
        }

        original_files[lock_path] = (
            lock_path.read_bytes()
        )

        report = inspect_interrupted_runs(
            runs_root=runs_root,
            lock_path=lock_path,
            now=now,
        )

        flagged = {
            item["run_id"]
            for item in report["candidates"]
        }

        assert old_running in flagged
        print("Old RUNNING run detected: PASS")

        assert old_reserved in flagged
        print("Old RESERVED run detected: PASS")

        assert recent_reserved not in flagged
        print("Recent RESERVED run preserved: PASS")

        assert completed not in flagged
        print("Completed run ignored: PASS")

        assert report["lock_state"] == (
            "REVIEW_REQUIRED"
        )

        print("Old execution lock detected: PASS")

        assert all(
            path.read_bytes() == content
            for path, content in original_files.items()
        )

        print("Existing fixture files unchanged: PASS")

    print("Temporary fixture cleanup: PASS")

    # Read-only inspection of actual API runtime.
    live_report = inspect_interrupted_runs()

    print()
    print("=== EXISTING API RUNTIME INSPECTION ===")
    print("Recorded workspaces:", live_report["runs_checked"])
    print("Recovery candidates:", len(
        live_report["candidates"]
    ))
    print("Execution lock:", live_report["lock_state"])

    for candidate in live_report["candidates"]:
        print("Review:", candidate)

    print()
    print("Automatic lock removal: NO")
    print("Existing run statuses modified: NO")
    print("Generator execution performed: NO")

    print()
    print("INTERRUPTED RUN INSPECTION TEST PASSED.")


if __name__ == "__main__":
    test_interruption_inspection()
