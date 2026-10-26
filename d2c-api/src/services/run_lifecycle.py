
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from src.config.simulation_config import (
    SimulationConfig,
    load_simulation_config,
)

from src.runtime.run_workspace import (
    RUN_ID_PATTERN,
)


# =====================================================
# PHASE 9.2.4B - RUN LIFECYCLE STATE MACHINE
# =====================================================

ALLOWED_TRANSITIONS = {
    "RESERVED": {"RUNNING", "FAILED"},
    "RUNNING": {"COMPLETED", "FAILED", "TIMED_OUT"},
    "COMPLETED": set(),
    "FAILED": set(),
    "TIMED_OUT": set(),
}

TERMINAL_STATUSES = {
    "COMPLETED",
    "FAILED",
    "TIMED_OUT",
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


# =====================================================
# CREATE INITIAL RUN RECORD
# =====================================================

def create_reserved_record(
    run_id: str,
    config: SimulationConfig,
):

    if (
        not isinstance(run_id, str)
        or not RUN_ID_PATTERN.fullmatch(run_id)
    ):
        raise ValueError("Invalid simulation run ID")

    if not isinstance(config, SimulationConfig):
        raise TypeError(
            "Validated SimulationConfig required"
        )

    return {
        "run_id": run_id,
        "status": "RESERVED",
        "days": config.days,
        "customers": config.customers,
        "scenario": config.scenario,
        "seed": config.seed,
        "created_at": utc_now(),
        "started_at": None,
        "finished_at": None,
        "exit_code": None,
        "generated_run_directory": None,
        "error": None,
    }


# =====================================================
# ENFORCE VALID STATE TRANSITIONS
# =====================================================

def transition_run_status(
    record,
    next_status,
    *,
    exit_code=None,
    generated_run_directory=None,
    error=None,
):

    if not isinstance(record, dict):
        raise TypeError("Run record must be a dictionary")

    current_status = record.get("status")

    if current_status not in ALLOWED_TRANSITIONS:
        raise ValueError(
            f"Unknown current status: {current_status}"
        )

    if next_status not in ALLOWED_TRANSITIONS:
        raise ValueError(
            f"Unknown next status: {next_status}"
        )

    if next_status not in ALLOWED_TRANSITIONS[current_status]:
        raise ValueError(
            f"Invalid transition: "
            f"{current_status} -> {next_status}"
        )

    if next_status == "COMPLETED":

        if type(exit_code) is not int or exit_code != 0:
            raise ValueError(
                "Completed run requires exit code 0"
            )

        if (
            not isinstance(generated_run_directory, str)
            or not generated_run_directory.strip()
        ):
            raise ValueError(
                "Completed run requires a dataset directory"
            )

    if next_status in {"FAILED", "TIMED_OUT"}:

        if not isinstance(error, str) or not error.strip():
            raise ValueError(
                "Failure requires a meaningful error message"
            )

    if exit_code is not None and type(exit_code) is not int:
        raise ValueError("Exit code must be an integer")

    updated = deepcopy(record)
    updated["status"] = next_status

    if next_status == "RUNNING":
        updated["started_at"] = utc_now()

    if next_status in TERMINAL_STATUSES:

        updated["finished_at"] = utc_now()
        updated["exit_code"] = exit_code
        updated["error"] = error

        if next_status == "COMPLETED":
            updated["generated_run_directory"] = (
                generated_run_directory
            )

    return updated


# =====================================================
# SELF-TEST
# =====================================================

def test_run_lifecycle():

    config = load_simulation_config()

    run_id = f"api_run_{uuid4().hex}"

    reserved = create_reserved_record(
        run_id,
        config,
    )

    assert reserved["status"] == "RESERVED"
    assert reserved["started_at"] is None

    print("Initial RESERVED state: PASS")

    running = transition_run_status(
        reserved,
        "RUNNING",
    )

    assert running["status"] == "RUNNING"
    assert running["started_at"] is not None
    assert reserved["status"] == "RESERVED"

    print("RESERVED -> RUNNING: PASS")
    print("Original record immutability: PASS")

    completed = transition_run_status(
        running,
        "COMPLETED",
        exit_code=0,
        generated_run_directory="data/generated/test_run",
    )

    assert completed["status"] == "COMPLETED"
    assert completed["finished_at"] is not None
    assert completed["exit_code"] == 0

    print("RUNNING -> COMPLETED: PASS")

    failed = transition_run_status(
        running,
        "FAILED",
        exit_code=1,
        error="Generator validation failed",
    )

    assert failed["status"] == "FAILED"

    print("RUNNING -> FAILED: PASS")

    timed_out = transition_run_status(
        running,
        "TIMED_OUT",
        error="Execution timeout exceeded",
    )

    assert timed_out["status"] == "TIMED_OUT"

    print("RUNNING -> TIMED_OUT: PASS")

    startup_failure = transition_run_status(
        reserved,
        "FAILED",
        error="Unable to start generator",
    )

    assert startup_failure["status"] == "FAILED"

    print("RESERVED -> FAILED: PASS")

    # -----------------------------------------------
    # Reject invalid state changes
    # -----------------------------------------------

    def expect_rejection(label, callback):

        try:
            callback()

        except ValueError:
            print(f"{label}: REJECTED (PASS)")

        else:
            raise AssertionError(
                f"Invalid operation accepted: {label}"
            )

    expect_rejection(
        "Duplicate RUNNING transition",
        lambda: transition_run_status(
            running, "RUNNING"
        ),
    )

    expect_rejection(
        "Completed run restart",
        lambda: transition_run_status(
            completed, "RUNNING"
        ),
    )

    expect_rejection(
        "Failed run restart",
        lambda: transition_run_status(
            failed, "RUNNING"
        ),
    )

    expect_rejection(
        "Completion without dataset",
        lambda: transition_run_status(
            running,
            "COMPLETED",
            exit_code=0,
        ),
    )

    expect_rejection(
        "Completion with nonzero exit code",
        lambda: transition_run_status(
            running,
            "COMPLETED",
            exit_code=1,
            generated_run_directory="data/generated/test_run",
        ),
    )

    expect_rejection(
        "Unknown lifecycle state",
        lambda: transition_run_status(
            reserved, "UNKNOWN"
        ),
    )

    print()
    print("Generator execution performed: NO")
    print("Existing run records modified: NO")
    print()
    print("RUN LIFECYCLE VALIDATION PASSED.")


if __name__ == "__main__":

    print("=" * 70)
    print("PHASE 9 - RUN LIFECYCLE STATE MACHINE")
    print("=" * 70)

    test_run_lifecycle()
