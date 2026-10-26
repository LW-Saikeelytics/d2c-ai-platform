
import json
import sys

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from src.runtime.run_workspace import (
    ROOT,
    RUNTIME_ROOT,
    RUN_ID_PATTERN,
)

from src.config.simulation_config import (
    load_simulation_config,
)

from src.services.run_lifecycle import (
    create_reserved_record,
    transition_run_status,
)


VALID_STATUSES = {
    "RESERVED",
    "RUNNING",
    "COMPLETED",
    "FAILED",
    "TIMED_OUT",
}

TERMINAL_STATUSES = {
    "COMPLETED",
    "FAILED",
    "TIMED_OUT",
}

TEST_RUN_ID = (
    "api_run_71e00acdec7c445fbee437ed68795f29"
)


def get_runtime_root():

    root = RUNTIME_ROOT.resolve()

    if (
        RUNTIME_ROOT.is_symlink()
        or not root.is_relative_to(ROOT.resolve())
    ):
        raise RuntimeError("Unsafe runtime root")

    return root


def validate_timestamp(value, field, required=False):

    if value is None:
        if required:
            raise ValueError(f"Missing timestamp: {field}")
        return None

    if not isinstance(value, str):
        raise ValueError(f"Invalid timestamp: {field}")

    parsed = datetime.fromisoformat(value)

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"Timezone missing: {field}")

    return parsed


# =====================================================
# RETRIEVE AND VALIDATE ONE RUN
# =====================================================

def get_run_status(run_id):

    if (
        not isinstance(run_id, str)
        or not RUN_ID_PATTERN.fullmatch(run_id)
    ):
        raise ValueError("Invalid simulation run ID")

    workspace = get_runtime_root() / run_id

    if workspace.is_symlink() or not workspace.is_dir():
        raise FileNotFoundError(
            f"Simulation run not found: {run_id}"
        )

    status_path = workspace / "execution_status.json"

    if status_path.is_symlink() or not status_path.is_file():
        raise FileNotFoundError(
            f"Execution status not found: {run_id}"
        )

    if status_path.stat().st_size > 131072:
        raise ValueError("Status file is too large")

    with status_path.open("r", encoding="utf-8") as file:
        record = json.load(file)

    if not isinstance(record, dict):
        raise ValueError("Invalid status document")

    if record.get("run_id") != run_id:
        raise ValueError("Status run ID mismatch")

    status = record.get("status")

    if status not in VALID_STATUSES:
        raise ValueError("Unknown execution status")

    for field in ("days", "customers"):
        value = record.get(field)

        if type(value) is not int or value <= 0:
            raise ValueError(f"Invalid field: {field}")

    if not isinstance(record.get("scenario"), str):
        raise ValueError("Invalid scenario metadata")

    created = validate_timestamp(
        record.get("created_at"),
        "created_at",
        required=(status == "RESERVED"),
    )

    started = validate_timestamp(
        record.get("started_at"),
        "started_at",
        required=status in {
            "RUNNING", "COMPLETED", "TIMED_OUT"
        },
    )

    finished = validate_timestamp(
        record.get("finished_at"),
        "finished_at",
        required=status in TERMINAL_STATUSES,
    )

    if created and started and created > started:
        raise ValueError("Run started before creation")

    if started and finished and started > finished:
        raise ValueError("Run finished before starting")

    if created and finished and created > finished:
        raise ValueError("Run finished before creation")

    if status == "RESERVED":

        if any(
            record.get(field) is not None
            for field in (
                "started_at",
                "finished_at",
                "exit_code",
                "generated_run_directory",
            )
        ):
            raise ValueError("Invalid RESERVED record")

    elif status == "RUNNING":

        if (
            finished is not None
            or record.get("exit_code") is not None
        ):
            raise ValueError("Invalid RUNNING record")

    elif status == "COMPLETED":

        if (
            type(record.get("exit_code")) is not int
            or record["exit_code"] != 0
        ):
            raise ValueError("Invalid completion exit code")

        generated = record.get("generated_run_directory")

        if not isinstance(generated, str) or not generated:
            raise ValueError("Missing generated dataset")

    elif status in {"FAILED", "TIMED_OUT"}:

        error = record.get("error")

        if not isinstance(error, str) or not error.strip():
            raise ValueError("Missing failure explanation")

    return record


# =====================================================
# LIST RUN HISTORY
# =====================================================

def list_run_history():

    runtime_root = get_runtime_root()

    if not runtime_root.is_dir():
        return []

    history = []

    for workspace in runtime_root.iterdir():

        if (
            workspace.is_symlink()
            or not workspace.is_dir()
            or not RUN_ID_PATTERN.fullmatch(workspace.name)
        ):
            continue

        if not (
            workspace / "execution_status.json"
        ).exists():
            continue

        record = get_run_status(workspace.name)

        history.append({
            "run_id": record["run_id"],
            "status": record["status"],
            "scenario": record["scenario"],
            "days": record["days"],
            "customers": record["customers"],
            "created_at": record.get("created_at"),
            "started_at": record.get("started_at"),
            "finished_at": record.get("finished_at"),
            "exit_code": record.get("exit_code"),
        })

    def sort_key(item):
        timestamp = (
            item["started_at"]
            or item["created_at"]
        )
        return datetime.fromisoformat(timestamp).timestamp()

    history.sort(key=sort_key, reverse=True)

    return history


# =====================================================
# COMPATIBILITY SELF-TEST
# =====================================================

def test_run_history():

    previous = get_run_status(TEST_RUN_ID)

    assert previous["status"] == "COMPLETED"
    assert previous["exit_code"] == 0

    print("Existing historical run compatibility: PASS")

    history = list_run_history()

    assert any(
        item["run_id"] == TEST_RUN_ID
        for item in history
    )

    print("Existing run-history discovery: PASS")

    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)

    # Temporary fixtures, isolated from the two real runs.
    with TemporaryDirectory(
        prefix="m14_history_fixture_",
        dir=RUNTIME_ROOT,
    ) as directory:

        fixture_root = Path(directory)
        run_id = f"api_run_{uuid4().hex}"

        workspace = fixture_root / run_id
        workspace.mkdir()

        status_file = workspace / "execution_status.json"

        config = load_simulation_config()

        reserved = create_reserved_record(
            run_id, config
        )

        status_file.write_text(
            json.dumps(reserved, indent=2),
            encoding="utf-8",
        )

        # Redirect history reads only inside this test.
        with patch.object(
            sys.modules[__name__],
            "get_runtime_root",
            return_value=fixture_root,
        ):

            result = get_run_status(run_id)

            assert result["status"] == "RESERVED"
            assert result["started_at"] is None

            print("RESERVED status retrieval: PASS")

            fixture_history = list_run_history()

            assert len(fixture_history) == 1
            assert fixture_history[0]["status"] == "RESERVED"

            print("RESERVED history discovery: PASS")

            failed = transition_run_status(
                reserved,
                "FAILED",
                error="Simulated pre-execution failure",
            )

            status_file.write_text(
                json.dumps(failed, indent=2),
                encoding="utf-8",
            )

            result = get_run_status(run_id)

            assert result["status"] == "FAILED"
            assert result["started_at"] is None
            assert result["finished_at"] is not None

            print("Pre-execution failure retrieval: PASS")

            fixture_history = list_run_history()

            assert fixture_history[0]["status"] == "FAILED"

            print("FAILED history discovery: PASS")

    print("Temporary fixture cleanup: PASS")

    try:
        get_run_status("../unsafe")
    except ValueError:
        print("Unsafe run ID: REJECTED (PASS)")
    else:
        raise AssertionError("Unsafe run ID accepted")

    print()
    print("Existing recorded runs:")

    for item in history:
        print(
            f"{item['run_id']} | "
            f"{item['status']} | "
            f"{item['scenario']} | "
            f"{item['days']} days"
        )

    print()
    print("Total existing runs:", len(history))
    print("Generator execution performed: NO")
    print("Existing run records modified: NO")
    print()
    print("RUN HISTORY LIFECYCLE COMPATIBILITY PASSED.")


if __name__ == "__main__":

    print("=" * 70)
    print("PHASE 9 - RUN HISTORY LIFECYCLE COMPATIBILITY")
    print("=" * 70)

    test_run_history()