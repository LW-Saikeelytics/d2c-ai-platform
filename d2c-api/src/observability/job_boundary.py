
import subprocess
import uuid

from pathlib import Path

from src.observability.production_logger import (
    ProductionLogger,
)


ALLOWED_JOBS = {
    "generator",
    "ml",
}


def run_logged_job(
    job_name: str,
    command: list[str],
    cwd: Path,
    execute: bool = False,
    runner=None,
    logger=None,
) -> int | None:
    """
    Run an explicitly authorized job while
    recording structured lifecycle events.

    Default behavior is non-executing.

    Intended for use by a separately validated
    M14 command-line controller.
    """

    if job_name not in ALLOWED_JOBS:
        raise ValueError(
            "Unsupported M14 job"
        )

    if not isinstance(command, list) or not command:
        raise ValueError(
            "A non-empty command list is required"
        )

    if not all(
        isinstance(arg, str) and arg
        for arg in command
    ):
        raise ValueError(
            "Invalid command argument"
        )

    working_directory = Path(cwd)

    if not working_directory.is_dir():
        raise ValueError(
            "Working directory does not exist"
        )

    if type(execute) is not bool:
        raise ValueError(
            "execute must be a boolean"
        )

    # Safety guard: no subprocess execution
    # unless explicitly requested.
    if not execute:
        return None

    # Live subprocess execution is intentionally disabled.
    # Phase 10.2 only permits a caller-supplied runner,
    # used by isolated tests and trusted internal code.

    if runner is None:
        raise RuntimeError(
            "Live subprocess execution is disabled"
        )

    job_logger = logger or ProductionLogger(
        component=job_name,
    )

    execution_id = uuid.uuid4().hex

    job_logger.log_event(
        level="INFO",
        event="job_started",
        execution_id=execution_id,
    )

    process_runner = runner
    try:
        result = process_runner(
            command,
            cwd=str(working_directory),
            check=False,
        )

    except KeyboardInterrupt as error:

        job_logger.log_event(
            level="WARNING",
            event="job_interrupted",
            execution_id=execution_id,
            error=error,
        )

        raise

    except Exception as error:

        job_logger.log_event(
            level="ERROR",
            event="job_launch_failed",
            execution_id=execution_id,
            error=error,
        )

        raise

    if result.returncode == 0:

        job_logger.log_event(
            level="INFO",
            event="job_succeeded",
            execution_id=execution_id,
        )

    else:

        job_logger.log_event(
            level="ERROR",
            event="job_failed",
            execution_id=execution_id,
        )

    return result.returncode