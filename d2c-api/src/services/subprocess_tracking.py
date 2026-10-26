
import json
import os
import subprocess
import sys

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import psutil


# =====================================================
# PHASE 9.5.3C - GENERATOR PROCESS TRACKING
# =====================================================

METADATA_FILENAME = "generator_process.json"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


# =====================================================
# RECORD GENERATOR PROCESS IDENTITY
# =====================================================

def register_generator_process(process, workspace):

    workspace = Path(workspace)

    if workspace.is_symlink() or not workspace.is_dir():
        raise ValueError("Invalid process workspace")

    if not isinstance(process, subprocess.Popen):
        raise TypeError("A started subprocess is required")

    process_info = psutil.Process(process.pid)

    metadata = {
        "process_id": process.pid,
        "process_create_time": process_info.create_time(),
        "recorded_at": utc_now(),
    }

    metadata_path = workspace / METADATA_FILENAME

    # Exclusive creation prevents replacement of
    # an existing process identity record.

    with metadata_path.open(
        "x",
        encoding="utf-8",
    ) as file:

        json.dump(metadata, file, indent=2)
        file.flush()
        os.fsync(file.fileno())

    return metadata_path


# =====================================================
# INSPECT RECORDED GENERATOR PROCESS
# =====================================================

def inspect_generator_process(metadata_path):

    metadata_path = Path(metadata_path)

    if metadata_path.is_symlink():
        return "UNSAFE_LINK"

    if not metadata_path.is_file():
        return "MISSING_METADATA"

    try:

        if metadata_path.stat().st_size > 131072:
            return "INVALID_METADATA"

        metadata = json.loads(
            metadata_path.read_text(encoding="utf-8")
        )

        if not isinstance(metadata, dict):
            return "INVALID_METADATA"

        pid = metadata.get("process_id")
        created = metadata.get("process_create_time")

        if (
            type(pid) is not int
            or pid <= 0
            or type(created) not in (int, float)
            or created <= 0
        ):
            return "INVALID_METADATA"

    except (OSError, ValueError, TypeError):
        return "INVALID_METADATA"

    try:

        process = psutil.Process(pid)

        actual_created = process.create_time()

        # A PID can be reused by Windows.
        # Compare process creation times to detect
        # a different process using the same PID.

        if abs(actual_created - created) > 1.0:
            return "PID_REUSED"

        if (
            not process.is_running()
            or process.status() == psutil.STATUS_ZOMBIE
        ):
            return "NOT_RUNNING"

        return "RUNNING"

    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return "NOT_RUNNING"

    except (psutil.AccessDenied, OSError):
        return "UNKNOWN"


# =====================================================
# SELF-TEST WITH HARMLESS PYTHON SUBPROCESS
# =====================================================

def test_subprocess_tracking():

    print("=" * 70)
    print("PHASE 9 - GENERATOR SUBPROCESS TRACKING")
    print("=" * 70)

    with TemporaryDirectory(
        prefix="m14_process_tracking_"
    ) as directory:

        workspace = Path(directory)

        # This starts a harmless sleeping Python
        # process, NOT the Phase 6 generator.

        process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-c",
                "import time; time.sleep(30)",
            ],
            cwd=workspace,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        try:

            metadata_path = register_generator_process(
                process,
                workspace,
            )

            assert metadata_path.is_file()

            print("Child process identity recorded: PASS")

            assert inspect_generator_process(
                metadata_path
            ) == "RUNNING"

            print("Active child process detected: PASS")

            # Existing identity metadata cannot
            # be replaced by a second registration.

            try:
                register_generator_process(
                    process,
                    workspace,
                )

            except FileExistsError:
                print(
                    "Duplicate process registration: "
                    "REJECTED (PASS)"
                )

            else:
                raise AssertionError(
                    "Duplicate process registration accepted"
                )

            original = metadata_path.read_bytes()
            modified = json.loads(original)

            # Simulate another process having reused
            # the recorded PID.

            modified["process_create_time"] -= 3600

            metadata_path.write_text(
                json.dumps(modified),
                encoding="utf-8",
            )

            assert inspect_generator_process(
                metadata_path
            ) == "PID_REUSED"

            print("Reused process ID detected: PASS")

            # Restore original identity metadata.
            metadata_path.write_bytes(original)

            assert inspect_generator_process(
                metadata_path
            ) == "RUNNING"

            print("Original process identity verified: PASS")

            # Stop only the temporary test process.
            process.terminate()
            process.wait(timeout=10)

            assert inspect_generator_process(
                metadata_path
            ) == "NOT_RUNNING"

            print("Stopped child process detected: PASS")

            metadata_path.write_text(
                "{invalid json",
                encoding="utf-8",
            )

            assert inspect_generator_process(
                metadata_path
            ) == "INVALID_METADATA"

            print(
                "Malformed process metadata: "
                "REJECTED (PASS)"
            )

        finally:

            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)

    print("Temporary test process cleaned up: PASS")
    print("Temporary metadata cleaned up: PASS")

    print()
    print("Actual simulation execution: NO")
    print("Existing simulation records modified: NO")
    print("Automatic lock recovery: DISABLED")

    print()
    print("GENERATOR SUBPROCESS TRACKING TEST PASSED.")


if __name__ == "__main__":
    test_subprocess_tracking()