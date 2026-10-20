
import io
import sys
import tempfile

from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from . import output_reproducibility as checker
from .reproducibility_baseline import sha256_file



def run_command(flag):
    buffer = io.StringIO()

    with (
        patch.object(
            sys,
            "argv",
            ["output_reproducibility.py", flag]
        ),
        redirect_stdout(buffer)
    ):
        checker.main()

    return buffer.getvalue()

def expect_change_detected():

    try:
        run_command("--verify")
    except RuntimeError as error:

        if "OUTPUT REPRODUCIBILITY FAILED" not in str(error):
            raise AssertionError(
                f"Unexpected verification failure: {error}"
            )

        return

    raise AssertionError(
        "Output change was not detected"
    )


def expect_match():

    output = run_command("--verify")

    if (
        "Output baseline status: MATCHED"
        not in output
    ):
        raise AssertionError(
            "Expected unchanged output baseline"
        )


def test_change_detection():

    real_baseline = checker.OUTPUT_BASELINE

    if not real_baseline.is_file():
        raise RuntimeError(
            "Capture the real output baseline first"
        )

    real_hash_before = sha256_file(real_baseline)

    with tempfile.TemporaryDirectory(
        prefix="m14_output_change_test_"
    ) as folder:

        root = Path(folder)
        run_id = "isolated_test_run"
        run_folder = f"run_id={run_id}"

        raw = root / "data" / "raw" / run_folder
        processed = root / "data" / "processed" / run_folder
        analytics = root / "data" / "analytics" / run_folder
        parquet = root / "data" / "parquet" / run_folder

        for directory in [
            raw, processed, analytics, parquet
        ]:
            directory.mkdir(
                parents=True,
                exist_ok=True
            )

        raw_first = raw / "source_a.json"
        raw_second = raw / "source_b.json"
        processed_file = processed / "cleaned.json"
        analytics_file = analytics / "metrics.json"

        raw_first.write_text(
            '{"customer": 1}',
            encoding="utf-8"
        )

        raw_second.write_text(
            '{"customer": 2}',
            encoding="utf-8"
        )

        processed_file.write_text(
            '{"orders": 2}',
            encoding="utf-8"
        )

        analytics_file.write_text(
            '{"revenue": 100}',
            encoding="utf-8"
        )

        # Fingerprint fixtures only.
        # The scanner hashes file bytes;
        # it does not parse Parquet contents.

        for index in range(366):
            path = parquet / f"part-{index:04d}.parquet"

            path.write_bytes(
                f"mock-parquet-{index}".encode("utf-8")
            )

        test_baseline = (
            root / "reports" / "output_baseline.json"
        )

        # Run the real snapshot scanner against
        # isolated test files, with only the
        # unrelated input-provenance check mocked.

        with (
            patch.object(checker, "ROOT", root),
            patch.object(
                checker,
                "OUTPUT_BASELINE",
                test_baseline
            ),
            patch.object(
                checker,
                "verify_inputs",
                return_value={
                    "run_id": run_id,
                    "fingerprint_sha256":
                        "isolated-test-input"
                }
            )
        ):

            # 1. Capture temporary baseline.

            output = run_command("--capture")

            if "Output baseline status: CREATED" not in output:
                raise AssertionError(
                    "Temporary baseline creation failed"
                )

            print("Temporary baseline capture: PASS")

            # 2. Unchanged files must match.

            expect_match()
            print("Unchanged outputs accepted: PASS")

            # 3. Modify a real temporary file.

            original = raw_first.read_bytes()

            raw_first.write_bytes(
                original + b"-modified"
            )

            expect_change_detected()
            print("Modified output detected: PASS")

            # Restore the original content.

            raw_first.write_bytes(original)
            expect_match()
            print("Restored output accepted: PASS")

            # 4. Delete one tracked temporary file.

            deleted_content = raw_second.read_bytes()
            raw_second.unlink()

            expect_change_detected()
            print("Deleted output detected: PASS")

            raw_second.write_bytes(deleted_content)
            expect_match()

            # 5. Add an unexpected temporary file.

            extra = analytics / "unexpected.json"

            extra.write_text(
                '{"unexpected": true}',
                encoding="utf-8"
            )

            expect_change_detected()
            print("Added output detected: PASS")

            extra.unlink()
            expect_match()

            print("Recovery after changes: PASS")

    # Confirm our permanent baseline was untouched.

    if sha256_file(real_baseline) != real_hash_before:
        raise AssertionError(
            "Real output baseline was modified"
        )

    print("Production baseline preserved: PASS")
    print("Temporary test isolation: PASS")

    print()
    print("OUTPUT CHANGE DETECTION TEST PASSED.")


if __name__ == "__main__":

    print("=" * 70)
    print("PHASE 8 - OUTPUT CHANGE DETECTION TEST")
    print("=" * 70)

    test_change_detection()