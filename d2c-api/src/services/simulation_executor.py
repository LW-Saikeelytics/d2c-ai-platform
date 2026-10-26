
import subprocess

from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from src.config.simulation_config import (
    load_simulation_config,
)

from src.runtime.run_workspace import (
    RUNTIME_ROOT,
    RunWorkspace,
    _reserve_in,
)

from src.services.simulation_run_service import (
    build_launch_plan,
)


# =====================================================
# PHASE 9.2.3A - SINGLE-USE EXECUTION CLAIM
# =====================================================

def claim_execution(workspace: RunWorkspace):

    runtime_root = RUNTIME_ROOT.resolve()

    working_dir = (
        workspace.working_directory.resolve()
    )

    output_dir = (
        workspace.output_directory.resolve()
    )

    if not working_dir.is_relative_to(runtime_root):
        raise ValueError(
            "Workspace is outside the API runtime"
        )

    if working_dir.name != workspace.run_id:
        raise ValueError(
            "Workspace run ID mismatch"
        )

    if not working_dir.is_dir():
        raise FileNotFoundError(
            "Workspace directory does not exist"
        )

    if output_dir != (
        working_dir / "data" / "generated"
    ):
        raise ValueError(
            "Unexpected workspace output path"
        )

    if not output_dir.is_dir():
        raise FileNotFoundError(
            "Output directory does not exist"
        )

    claim_path = (
        working_dir / "execution.claim"
    )

    # Exclusive file creation is atomic.
    #
    # A second execution claim for the same
    # workspace raises FileExistsError.

    with claim_path.open(
        "x",
        encoding="utf-8"
    ) as file:

        file.write(
            f"run_id={workspace.run_id}\n"
        )

    return claim_path


# =====================================================
# PREFLIGHT SELF-TEST
# =====================================================

def test_execution_preflight():

    config = load_simulation_config()

    runtime_root = RUNTIME_ROOT.resolve()

    runtime_root.mkdir(
        parents=True,
        exist_ok=True
    )

    with TemporaryDirectory(
        prefix="phase9_preflight_",
        dir=runtime_root
    ) as temporary_root:

        workspace = _reserve_in(
            Path(temporary_root),
            f"api_run_{uuid4().hex}"
        )

        plan = build_launch_plan(
            config,
            workspace
        )

        print("Launch plan construction: PASS")

        assert (
            plan.working_directory
            .is_relative_to(runtime_root)
        )

        print("API runtime boundary: PASS")

        # ---------------------------------------
        # First execution claim
        # ---------------------------------------

        claim_path = claim_execution(
            workspace
        )

        assert claim_path.is_file()

        print("First execution claim: PASS")

        # ---------------------------------------
        # Duplicate claim must fail
        # ---------------------------------------

        try:
            claim_execution(workspace)

        except FileExistsError:
            print(
                "Duplicate execution claim: "
                "REJECTED (PASS)"
            )

        else:
            raise AssertionError(
                "Duplicate execution claim accepted"
            )

        # ---------------------------------------
        # Validate generator CLI without
        # starting a simulation
        # ---------------------------------------

        environment = plan.environment.copy()

        environment[
            "PYTHONDONTWRITEBYTECODE"
        ] = "1"

        environment[
            "PYTHONNOUSERSITE"
        ] = "1"

        help_command = [
            *plan.command,
            "--help"
        ]

        result = subprocess.run(
            help_command,
            cwd=plan.working_directory,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False
        )

        if result.returncode != 0:

            print(result.stdout)
            print(result.stderr)

            raise RuntimeError(
                "Generator CLI preflight failed"
            )

        for argument in (
            "--days",
            "--customers",
            "--scenario"
        ):

            assert argument in result.stdout, (
                f"CLI argument missing: {argument}"
            )

        print("Generator CLI compatibility: PASS")

        # The --help command must not generate
        # any simulation datasets.

        generated_items = list(
            plan.output_directory.iterdir()
        )

        assert not generated_items, (
            "Unexpected simulation output"
        )

        print("No simulation datasets created: PASS")

        print()
        print("Simulation execution performed: NO")

    print("Temporary workspace cleanup: PASS")

    print()
    print(
        "EXECUTION PREFLIGHT TEST PASSED."
    )


if __name__ == "__main__":

    print("=" * 70)
    print("PHASE 9 - EXECUTION SAFETY PREFLIGHT")
    print("=" * 70)

    test_execution_preflight()
