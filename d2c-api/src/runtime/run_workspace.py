
import re

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from src.config.simulation_config import ROOT


# =====================================================
# PHASE 9.1.3C - SAFE RUN WORKSPACE
# =====================================================

RUNTIME_ROOT = ROOT / "runtime" / "runs"

RUN_ID_PATTERN = re.compile(
    r"api_run_[0-9a-f]{32}"
)


@dataclass(frozen=True)
class RunWorkspace:

    run_id: str
    working_directory: Path
    output_directory: Path


# =====================================================
# ATOMIC WORKSPACE RESERVATION
# =====================================================

def _reserve_in(base_dir: Path, run_id: str):

    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError("Invalid internal run ID")

    base_dir = Path(base_dir).resolve()

    base_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    workspace_dir = base_dir / run_id

    # Exclusive creation:
    # reject an existing workspace rather than reuse it.
    workspace_dir.mkdir(
        exist_ok=False
    )

    # Mirrors the Phase 6 writer's relative output path.
    output_dir = (
        workspace_dir
        / "data"
        / "generated"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=False
    )

    return RunWorkspace(
        run_id=run_id,
        working_directory=workspace_dir,
        output_directory=output_dir
    )


# =====================================================
# PRODUCTION WORKSPACE FACTORY
# =====================================================

def reserve_run_workspace():

    app_root = ROOT.resolve()

    runtime_root = RUNTIME_ROOT.resolve()

    # Prevent runtime files from escaping
    # the dedicated Phase 9 project.
    if not runtime_root.is_relative_to(app_root):
        raise RuntimeError(
            "Runtime directory escapes the API project"
        )

    for _ in range(5):

        run_id = f"api_run_{uuid4().hex}"

        try:
            return _reserve_in(
                RUNTIME_ROOT,
                run_id
            )

        except FileExistsError:
            continue

    raise RuntimeError(
        "Unable to reserve a unique run workspace"
    )


# =====================================================
# SAFE ISOLATION SELF-TEST
# =====================================================

def test_run_isolation():

    with TemporaryDirectory(
        prefix="m14_run_isolation_"
    ) as temporary_root:

        test_root = Path(temporary_root)

        first = _reserve_in(
            test_root,
            f"api_run_{uuid4().hex}"
        )

        second = _reserve_in(
            test_root,
            f"api_run_{uuid4().hex}"
        )

        assert first.run_id != second.run_id

        assert (
            first.working_directory
            != second.working_directory
        )

        assert (
            first.output_directory
            != second.output_directory
        )

        print("Unique run identifiers: PASS")
        print("Independent workspaces: PASS")

        for workspace in (first, second):

            assert workspace.working_directory.is_dir()
            assert workspace.output_directory.is_dir()

            assert (
                workspace.output_directory
                == workspace.working_directory
                / "data"
                / "generated"
            )

            assert (
                workspace.working_directory.resolve()
                .is_relative_to(test_root.resolve())
            )

        print("Relative output directory isolation: PASS")

        # Existing run directories cannot be reused.
        try:
            _reserve_in(
                test_root,
                first.run_id
            )

        except FileExistsError:
            print("Run directory collision: REJECTED (PASS)")

        else:
            raise AssertionError(
                "Existing workspace was reused"
            )

        # Invalid identifiers cannot traverse paths.
        try:
            _reserve_in(
                test_root,
                "../unsafe"
            )

        except ValueError:
            print("Unsafe run identifier: REJECTED (PASS)")

        else:
            raise AssertionError(
                "Unsafe run identifier was accepted"
            )

        frozen_output = (
            ROOT.parent
            / "d2c-synthetic-data"
            / "data"
            / "generated"
        ).resolve()

        for workspace in (first, second):

            assert not (
                workspace.output_directory.resolve()
                .is_relative_to(frozen_output)
            )

        print("Phase 6 output separation: PASS")

    print("Temporary test workspace cleanup: PASS")
    print("Generator execution performed: NO")
    print()
    print("RUN WORKSPACE ISOLATION TEST PASSED.")


if __name__ == "__main__":

    print("=" * 70)
    print("PHASE 9 - RUN WORKSPACE ISOLATION")
    print("=" * 70)

    test_run_isolation()