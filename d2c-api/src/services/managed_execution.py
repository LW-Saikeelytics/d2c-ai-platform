
import subprocess
import sys

from pathlib import Path

from src.config.simulation_config import (
    SimulationConfig,
    load_simulation_config,
)

from src.api.simulation_start_request import (
    SimulationStartRequest,
)

from src.runtime.run_workspace import (
    RUNTIME_ROOT,
    reserve_run_workspace,
)

from src.services.simulation_run_service import (
    build_launch_plan,
)

from src.services.simulation_executor import (
    claim_execution,
)

from src.services.execution_lock import (
    LOCK_PATH,
    simulation_execution_slot,
)

from src.services.subprocess_tracking import (
    register_generator_process,
    inspect_generator_process,
)

from src.services.run_lifecycle import (
    create_reserved_record,
    transition_run_status,
)

from src.services.controlled_execution import (
    TIMEOUT_SECONDS,
    save_status,
    validate_generated_outputs,
)


# =====================================================
# STOP A GENERATOR PROCESS AFTER AN ERROR OR TIMEOUT
# =====================================================

def stop_generator(process):

    if process is None or process.poll() is not None:
        return

    process.terminate()

    try:
        process.wait(timeout=5)

    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


# =====================================================
# MANAGED SIMULATION EXECUTION
# =====================================================

def run_managed_simulation(config):

    if not isinstance(config, SimulationConfig):
        raise TypeError("SimulationConfig required")

    # Enforce API workload limits even if this
    # function is called outside FastAPI.
    request = SimulationStartRequest.model_validate(
        config.model_dump()
    )

    config = request.to_simulation_config()

    holder = {"process": None}

    def can_release_lock():
        process = holder["process"]

        return (
            process is None
            or process.poll() is not None
        )

    # Only one cooperating API execution process
    # can hold this slot at a time.
    with simulation_execution_slot(
        can_release=can_release_lock
    ):

        workspace = reserve_run_workspace()

        plan = build_launch_plan(
            config,
            workspace,
        )

        cwd = plan.working_directory.resolve()

        if cwd.parent != RUNTIME_ROOT.resolve():
            raise RuntimeError(
                "Unsafe execution workspace"
            )

        if any(plan.output_directory.iterdir()):
            raise RuntimeError(
                "Output directory must be empty"
            )

        claim_execution(workspace)

        status_path = cwd / "execution_status.json"
        log_path = cwd / "execution.log"
        metadata_path = cwd / "generator_process.json"

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

            record = transition_run_status(
                record,
                "RUNNING",
            )

            save_status(status_path, record)

            with log_path.open(
                "w",
                encoding="utf-8",
            ) as log_file:

                process = subprocess.Popen(
                    command,
                    cwd=cwd,
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                )

                holder["process"] = process

                # Record the real generator PID.
                register_generator_process(
                    process,
                    cwd,
                )

                exit_code = process.wait(
                    timeout=TIMEOUT_SECONDS
                )

            if exit_code != 0:
                raise RuntimeError(
                    f"Generator exited with code {exit_code}"
                )

            # The subprocess has finished.
            # Verify that process tracking agrees.
            process_state = inspect_generator_process(
                metadata_path
            )

            if process_state != "NOT_RUNNING":
                raise RuntimeError(
                    "Generator process termination "
                    f"could not be verified: {process_state}"
                )

            generated_run = validate_generated_outputs(
                plan.output_directory,
                config.scenario,
            )

            record = transition_run_status(
                record,
                "COMPLETED",
                exit_code=0,
                generated_run_directory=str(
                    generated_run
                ),
            )

        except subprocess.TimeoutExpired:

            record = transition_run_status(
                record,
                "TIMED_OUT",
                error=(
                    f"Execution exceeded "
                    f"{TIMEOUT_SECONDS} seconds"
                ),
            )

        except Exception as exc:

            record = transition_run_status(
                record,
                "FAILED",
                exit_code=exit_code,
                error=f"{type(exc).__name__}: {exc}",
            )

        finally:

            try:
                # Never intentionally leave the
                # generator running after the
                # managed execution scope.
                stop_generator(holder["process"])

            finally:
                save_status(status_path, record)

        return record, workspace


# =====================================================
# INTEGRATION TEST
# =====================================================

def test_managed_execution():

    config = load_simulation_config()

    print("=" * 70)
    print("PHASE 9 - MANAGED SIMULATION EXECUTION")
    print("=" * 70)

    print("Scenario:", config.scenario)
    print("Days:", config.days)
    print("Customers:", config.customers)

    record, workspace = run_managed_simulation(
        config
    )

    print()
    print("API Run ID:", workspace.run_id)
    print("Execution status:", record["status"])
    print("Exit code:", record["exit_code"])

    print(
        "Workspace:",
        workspace.working_directory,
    )

    if record["status"] != "COMPLETED":

        print("Failure:", record["error"])

        log_path = (
            workspace.working_directory
            / "execution.log"
        )

        if log_path.is_file():

            print()
            print("=== GENERATOR LOG: LAST 30 LINES ===")

            lines = log_path.read_text(
                encoding="utf-8",
                errors="replace",
            ).splitlines()

            for line in lines[-30:]:
                print(line)

        raise RuntimeError(
            "Managed simulation execution failed"
        )

    print("Managed generator execution: PASS")

    metadata_path = (
        workspace.working_directory
        / "generator_process.json"
    )

    assert metadata_path.is_file()

    print("Generator PID metadata recorded: PASS")

    assert (
        inspect_generator_process(metadata_path)
        == "NOT_RUNNING"
    )

    print("Generator termination verified: PASS")

    assert not LOCK_PATH.exists()

    print("Concurrency lock released: PASS")

    assert Path(
        record["generated_run_directory"]
    ).is_dir()

    print("Generated dataset available: PASS")

    print()
    print("MANAGED SIMULATION INTEGRATION TEST PASSED.")


if __name__ == "__main__":
    test_managed_execution()
