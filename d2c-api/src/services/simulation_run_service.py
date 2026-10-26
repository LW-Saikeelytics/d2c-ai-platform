
import os
import sys

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from src.config.simulation_config import (
    ROOT,
    SimulationConfig,
    load_simulation_config,
    build_runner_arguments,
)

from src.config.scenario_registry import (
    validate_scenario,
)

from src.runtime.run_workspace import (
    RunWorkspace,
    _reserve_in,
)


GENERATOR_ROOT = (
    ROOT.parent / "d2c-synthetic-data"
).resolve()

PLATFORM_ROOT = (
    ROOT.parent / "d2c-data-platform"
).resolve()

GENERATOR_MODULE = (
    "simulation.production_dataset_runner"
)


@dataclass(frozen=True)
class SimulationLaunchPlan:
    command: tuple[str, ...]
    working_directory: Path
    output_directory: Path
    environment: dict[str, str]


# =====================================================
# PHASE 9.2.1 - SAFE LAUNCH PLAN
# =====================================================

def build_launch_plan(
    config: SimulationConfig,
    workspace: RunWorkspace,
    python_executable=None,
):

    if not isinstance(config, SimulationConfig):
        raise TypeError(
            "A validated SimulationConfig is required"
        )

    # Validate against the real Phase 6 registry.
    validate_scenario(config)

    entrypoint = (
        GENERATOR_ROOT
        / "simulation"
        / "production_dataset_runner.py"
    )

    if not entrypoint.is_file():
        raise FileNotFoundError(
            f"Generator entrypoint missing: {entrypoint}"
        )

    cwd = workspace.working_directory.resolve()
    output_dir = workspace.output_directory.resolve()

    if not cwd.is_dir() or not output_dir.is_dir():
        raise ValueError(
            "Reserved workspace directories are missing"
        )

    expected_output = (
        cwd / "data" / "generated"
    ).resolve()

    if output_dir != expected_output:
        raise ValueError(
            "Unexpected simulation output directory"
        )

    if (
        cwd.is_relative_to(GENERATOR_ROOT)
        or cwd.is_relative_to(PLATFORM_ROOT)
    ):
        raise ValueError(
            "Execution workspace overlaps a frozen project"
        )

    interpreter = Path(
        python_executable or sys.executable
    ).resolve()

    if not interpreter.is_file():
        raise FileNotFoundError(
            f"Python interpreter missing: {interpreter}"
        )

    command = (
        str(interpreter),
        "-m",
        GENERATOR_MODULE,
        *build_runner_arguments(config),
    )

    environment = os.environ.copy()

    # Make the existing Phase 6 package importable
    # while running from the isolated workspace.
    environment["PYTHONPATH"] = str(
        GENERATOR_ROOT
    )

    return SimulationLaunchPlan(
        command=command,
        working_directory=cwd,
        output_directory=output_dir,
        environment=environment,
    )


# =====================================================
# SELF-TEST: NO SIMULATION EXECUTION
# =====================================================

def test_launch_planner():

    config = load_simulation_config()

    with TemporaryDirectory(
        prefix="m14_launch_test_"
    ) as temporary_root:

        workspace = _reserve_in(
            Path(temporary_root),
            f"api_run_{uuid4().hex}",
        )

        plan = build_launch_plan(
            config,
            workspace,
        )

        assert plan.working_directory == (
            workspace.working_directory.resolve()
        )

        print("Isolated working directory: PASS")

        assert plan.output_directory == (
            plan.working_directory
            / "data"
            / "generated"
        )

        print("Isolated output directory: PASS")

        assert plan.command[1:3] == (
            "-m",
            GENERATOR_MODULE,
        )

        assert plan.command[3:] == tuple(
            build_runner_arguments(config)
        )

        print("Generator command construction: PASS")

        assert Path(
            plan.environment["PYTHONPATH"]
        ).resolve() == GENERATOR_ROOT

        print("Generator import path configuration: PASS")

        assert not (
            plan.working_directory
            .is_relative_to(GENERATOR_ROOT)
        )

        assert not (
            plan.working_directory
            .is_relative_to(PLATFORM_ROOT)
        )

        print("Frozen project separation: PASS")

        invalid = SimulationConfig(
            days=7,
            customers=100,
            scenario="unknown_scenario",
            seed=42,
        )

        try:
            build_launch_plan(
                invalid,
                workspace,
            )

        except ValueError:
            print("Unsupported scenario: REJECTED (PASS)")

        else:
            raise AssertionError(
                "Unsupported scenario was accepted"
            )

        print()
        print("Prepared command:")
        print(" ".join(plan.command))

        print()
        print("Working directory:")
        print(plan.working_directory)

        print()
        print("Generator execution performed: NO")
        print("Subprocess created: NO")

    print("Temporary workspace cleanup: PASS")
    print()
    print("SIMULATION LAUNCH PLAN TEST PASSED.")


if __name__ == "__main__":

    print("=" * 70)
    print("PHASE 9 - SIMULATION LAUNCH PLANNER")
    print("=" * 70)

    test_launch_planner()
