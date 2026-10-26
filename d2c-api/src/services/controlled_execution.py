
import json
import os
import subprocess
import sys

from datetime import datetime, timezone
from pathlib import Path

from src.config.simulation_config import (
    load_simulation_config,
)
from src.runtime.run_workspace import (
    ROOT,
    RUNTIME_ROOT,
    reserve_run_workspace,
)
from src.services.simulation_run_service import (
    build_launch_plan,
)
from src.services.simulation_executor import (
    claim_execution,
)

from src.services.run_lifecycle import (
    create_reserved_record,
    transition_run_status,
)

TIMEOUT_SECONDS = 600


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def save_status(path, record):
    """Atomically update the execution status."""

    temporary = path.with_suffix(".tmp")

    temporary.write_text(
        json.dumps(record, indent=2),
        encoding="utf-8",
    )

    os.replace(temporary, path)


def validate_generated_outputs(output_root, scenario):
    """Verify the expected Phase 6 output manifests."""

    run_directories = [
        path
        for path in output_root.iterdir()
        if path.is_dir()
        and path.name.startswith("simulation_run_")
    ]

    if len(run_directories) != 1:
        raise RuntimeError(
            "Expected exactly one generated simulation directory; "
            f"found {len(run_directories)}"
        )

    generated_run = run_directories[0]

    if (
        generated_run.is_symlink()
        or generated_run.resolve().parent
        != output_root.resolve()
    ):
        raise RuntimeError("Unsafe generated run directory")

    required_files = [
        "simulation_manifest.json",
        "simulation_scenario.json",
        "dataset_freeze_manifest.json",
        "analytics/analytics_manifest.json",
    ]

    for filename in required_files:
        file_path = generated_run / filename

        if not file_path.is_file():
            raise RuntimeError(
                f"Required output missing: {filename}"
            )

        if (
            file_path.is_symlink()
            or not file_path.resolve().is_relative_to(
                generated_run.resolve()
            )
        ):
            raise RuntimeError(
                f"Unsafe output file: {filename}"
            )

        with file_path.open(
            "r", encoding="utf-8"
        ) as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise RuntimeError(
                f"Invalid output manifest: {filename}"
            )

        if filename == "simulation_manifest.json":
            if data.get("run_id") != generated_run.name:
                raise RuntimeError(
                    "Generated run ID does not match manifest"
                )

        if filename == "simulation_scenario.json":
            if data.get("name") != scenario:
                raise RuntimeError(
                    "Generated scenario does not match request"
                )

    return generated_run



def execute_simulation(config, workspace):
    """Execute a simulation using enforced lifecycle transitions."""

    plan = build_launch_plan(config, workspace)

    runtime_root = RUNTIME_ROOT.resolve()
    cwd = plan.working_directory.resolve()
    output_root = plan.output_directory.resolve()

    if not runtime_root.is_relative_to(ROOT.resolve()):
        raise RuntimeError("Unsafe API runtime root")

    if cwd.parent != runtime_root:
        raise RuntimeError(
            "Execution requires a directly reserved API workspace"
        )

    if (
        output_root.parent.parent != cwd
        or not output_root.is_relative_to(cwd)
    ):
        raise RuntimeError("Unsafe output directory")

    if any(output_root.iterdir()):
        raise RuntimeError(
            "Execution requires an empty output directory"
        )

    # Claim first. A duplicate invocation must not
    # overwrite the existing run's status record.
    claim_execution(workspace)

    status_path = cwd / "execution_status.json"
    log_path = cwd / "execution.log"

    # ---------------------------------------------
    # STATE 1: RESERVED
    # ---------------------------------------------

    record = create_reserved_record(
        workspace.run_id,
        config,
    )

    save_status(status_path, record)

    environment = plan.environment.copy()

    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"

    command = [
        plan.command[0],
        "-B",
        *plan.command[1:],
    ]

    exit_code = None

    try:

        # -----------------------------------------
        # STATE 2: RUNNING
        # -----------------------------------------

        record = transition_run_status(
            record,
            "RUNNING",
        )

        save_status(status_path, record)

        with log_path.open(
            "w",
            encoding="utf-8",
        ) as log_file:

            result = subprocess.run(
                command,
                cwd=cwd,
                env=environment,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                timeout=TIMEOUT_SECONDS,
                check=False,
            )

        exit_code = result.returncode

        if exit_code != 0:
            raise RuntimeError(
                f"Generator exited with code {exit_code}"
            )

        generated_run = validate_generated_outputs(
            output_root,
            config.scenario,
        )

        # -----------------------------------------
        # STATE 3A: COMPLETED
        # -----------------------------------------

        record = transition_run_status(
            record,
            "COMPLETED",
            exit_code=0,
            generated_run_directory=str(
                generated_run
            ),
        )

    except subprocess.TimeoutExpired:

        # -----------------------------------------
        # STATE 3B: TIMED_OUT
        # -----------------------------------------

        record = transition_run_status(
            record,
            "TIMED_OUT",
            error=(
                f"Execution exceeded "
                f"{TIMEOUT_SECONDS} seconds"
            ),
        )

    except Exception as exc:

        # -----------------------------------------
        # STATE 3C: FAILED
        # -----------------------------------------

        record = transition_run_status(
            record,
            "FAILED",
            exit_code=exit_code,
            error=(
                f"{type(exc).__name__}: {exc}"
            ),
        )

    finally:

        # Persist terminal status.
        save_status(status_path, record)

    return record, log_path, status_path

def main():

    print("=" * 70)
    print("PHASE 9 - FIRST CONTROLLED SIMULATION")
    print("=" * 70)

    config = load_simulation_config()

    workspace = reserve_run_workspace()

    print("API Run ID:", workspace.run_id)
    print("Scenario:", config.scenario)
    print("Days:", config.days)
    print("Customers:", config.customers)
    print("Workspace:", workspace.working_directory)
    print()

    record, log_path, status_path = execute_simulation(
        config,
        workspace,
    )

    print("Execution status:", record["status"])
    print("Exit code:", record["exit_code"])
    print("Execution log:", log_path)
    print("Status file:", status_path)

    if record["status"] == "COMPLETED":

        print(
            "Generated dataset:",
            record["generated_run_directory"],
        )

        print()
        print("CONTROLLED SIMULATION EXECUTION PASSED.")

    else:

        print()
        print("Failure reason:", record["error"])

        if log_path.is_file():

            print()
            print("=== GENERATOR LOG: LAST 40 LINES ===")

            lines = log_path.read_text(
                encoding="utf-8",
                errors="replace",
            ).splitlines()

            for line in lines[-40:]:
                print(line)

        print()
        print("CONTROLLED SIMULATION REQUIRES INVESTIGATION.")
        sys.exit(1)


if __name__ == "__main__":
    main()
