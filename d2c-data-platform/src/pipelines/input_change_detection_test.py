
import json
import tempfile

from pathlib import Path
from unittest.mock import patch

from . import reproducibility_baseline as baseline
from . import output_reproducibility as checker
from .reproducibility_baseline import sha256_file


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True),
        encoding="utf-8"
    )


def expect_failure(message):
    try:
        checker.verify_inputs()
    except RuntimeError as error:
        if message not in str(error):
            raise AssertionError(
                f"Unexpected failure: {error}"
            ) from error
        return

    raise AssertionError(
        f"Expected rejection containing: {message}"
    )


def expect_match(expected_baseline):
    actual = checker.verify_inputs()

    if actual != expected_baseline:
        raise AssertionError(
            "Restored input baseline does not match"
        )


def test_file_modification(
    path, replacement, expected_error,
    expected_baseline
):
    original = path.read_bytes()

    try:
        path.write_bytes(replacement)
        expect_failure(expected_error)
    finally:
        path.write_bytes(original)

    expect_match(expected_baseline)


def run_test():

    # Protect our real saved baseline reports.

    real_reports = [
        baseline.BASELINE_PATH,
        checker.OUTPUT_BASELINE,
        checker.SEED_REPORT
    ]

    original_hashes = {}

    for path in real_reports:
        if not path.is_file():
            raise RuntimeError(
                f"Missing real baseline report: {path}"
            )

        original_hashes[path] = sha256_file(path)

    with tempfile.TemporaryDirectory(
        prefix="m14_input_change_test_"
    ) as folder:

        workspace = Path(folder)

        platform_root = (
            workspace / "d2c-data-platform"
        )

        run_id = "isolated_input_test_run"

        raw_dir = (
            platform_root / "data" / "raw"
            / f"run_id={run_id}"
        )

        raw_dir.mkdir(parents=True)

        # --------------------------------------
        # CREATE 25 TEMPORARY RAW FILES
        # --------------------------------------

        raw_files = []

        for index in range(25):
            path = raw_dir / f"source_{index:02d}.jsonl"

            path.write_text(
                json.dumps({"row": index}) + "\n",
                encoding="utf-8"
            )

            raw_files.append(path)

        write_json(
            raw_dir / "_raw_manifest.json",
            {"run_id": run_id}
        )

        # --------------------------------------
        # TEMPORARY CONFIGURATION FILES
        # --------------------------------------

        platform_config = (
            platform_root / "config"
            / "platform_config.json"
        )

        database_config = (
            platform_root / "config"
            / "database_config.json"
        )

        schema_path = (
            platform_root / "schemas"
            / "canonical_schema.json"
        )

        write_json(
            platform_config,
            {
                "source": {"run_id": run_id},
                "pipeline": {"batch_size": 1000}
            }
        )

        write_json(
            database_config,
            {
                "host": "localhost",
                "port": 5432
            }
        )

        write_json(
            schema_path,
            {
                "version": 1,
                "entities": ["orders"]
            }
        )

        # --------------------------------------
        # TEMPORARY GENERATOR SOURCE
        # --------------------------------------

        generator_path = (
            workspace
            / "d2c-synthetic-data"
            / "simulation"
            / "production_dataset_runner.py"
        )

        generator_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        generator_path.write_text(
            "# isolated generator fixture\n"
            "SEED = 42\n",
            encoding="utf-8"
        )

        baseline_path = (
            platform_root / "reports"
            / "reproducibility_baseline.json"
        )

        seed_report = (
            platform_root / "reports"
            / "seed_provenance.json"
        )

        # Redirect the actual validation code
        # to our disposable test workspace.

        with (
            patch.object(
                baseline, "ROOT", platform_root
            ),
            patch.object(
                checker, "ROOT", platform_root
            ),
            patch.object(
                checker, "BASELINE_PATH",
                baseline_path
            ),
            patch.object(
                checker, "SEED_REPORT",
                seed_report
            )
        ):

            # ----------------------------------
            # 1. CAPTURE TEMPORARY BASELINE
            # ----------------------------------

            expected = baseline.build_baseline()

            if (
                expected["raw_source_file_count"] != 25
                or expected["input_file_count"] != 29
            ):
                raise AssertionError(
                    "Unexpected fixture input counts"
                )

            write_json(baseline_path, expected)

            relative_generator = (
                generator_path
                .relative_to(workspace)
                .as_posix()
            )

            write_json(
                seed_report,
                {
                    "source_run_id": run_id,
                    "input_fingerprint_sha256":
                        expected["fingerprint_sha256"],
                    "generator_source_sha256": {
                        relative_generator:
                            sha256_file(generator_path)
                    }
                }
            )

            expect_match(expected)

            print("Temporary input baseline: PASS")
            print("Unchanged configuration accepted: PASS")

            # ----------------------------------
            # 2. MODIFY RAW SOURCE CONTENT
            # ----------------------------------

            test_file_modification(
                raw_files[0],
                b'{"row": 999}\n',
                "Frozen input baseline has changed",
                expected
            )

            print("Raw source modification detected: PASS")

            # ----------------------------------
            # 3. CHANGE PLATFORM CONFIGURATION
            # ----------------------------------

            changed_platform_config = {
                "source": {"run_id": run_id},
                "pipeline": {"batch_size": 500}
            }

            test_file_modification(
                platform_config,
                json.dumps(
                    changed_platform_config
                ).encode("utf-8"),
                "Frozen input baseline has changed",
                expected
            )

            print("Platform configuration drift detected: PASS")

            # ----------------------------------
            # 4. CHANGE DATABASE CONFIGURATION
            # ----------------------------------

            test_file_modification(
                database_config,
                json.dumps({
                    "host": "different-host",
                    "port": 5432
                }).encode("utf-8"),
                "Frozen input baseline has changed",
                expected
            )

            print("Database configuration drift detected: PASS")

            # ----------------------------------
            # 5. CHANGE CANONICAL SCHEMA
            # ----------------------------------

            test_file_modification(
                schema_path,
                json.dumps({
                    "version": 2,
                    "entities": ["orders"]
                }).encode("utf-8"),
                "Frozen input baseline has changed",
                expected
            )

            print("Canonical schema drift detected: PASS")

            # ----------------------------------
            # 6. REMOVE AN INPUT FILE
            # ----------------------------------

            removed = raw_files[1]
            original_content = removed.read_bytes()

            try:
                removed.unlink()

                expect_failure(
                    "Expected 25 raw source files"
                )
            finally:
                removed.write_bytes(original_content)

            expect_match(expected)

            print("Missing source file detected: PASS")

            # ----------------------------------
            # 7. ADD AN UNEXPECTED INPUT
            # ----------------------------------

            extra = raw_dir / "unexpected.jsonl"

            try:
                extra.write_text(
                    '{"unexpected": true}\n',
                    encoding="utf-8"
                )

                expect_failure(
                    "Expected 25 raw source files"
                )
            finally:
                extra.unlink(missing_ok=True)

            expect_match(expected)

            print("Unexpected source file detected: PASS")

            # ----------------------------------
            # 8. MODIFY GENERATOR SOURCE CODE
            # ----------------------------------

            test_file_modification(
                generator_path,
                b"# changed generator fixture\nSEED = 99\n",
                "Generator source changed",
                expected
            )

            print("Generator source drift detected: PASS")

            # ----------------------------------
            # 9. FINAL RESTORATION CHECK
            # ----------------------------------

            expect_match(expected)

            print("Restored inputs accepted: PASS")

    # Verify real reports remain unchanged.

    for path, original_hash in original_hashes.items():
        if sha256_file(path) != original_hash:
            raise AssertionError(
                f"Real baseline modified: {path}"
            )

    print("Production baselines preserved: PASS")
    print("Temporary test isolation: PASS")

    print()
    print(
        "INPUT AND CONFIGURATION "
        "CHANGE DETECTION TEST PASSED."
    )


if __name__ == "__main__":

    print("=" * 70)
    print(
        "PHASE 8 - INPUT AND CONFIGURATION "
        "CHANGE DETECTION"
    )
    print("=" * 70)

    run_test()