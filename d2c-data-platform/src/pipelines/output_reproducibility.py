
import argparse
import hashlib
import json

from .pipeline_logger import ROOT
from .reproducibility_baseline import (
    BASELINE_PATH,
    build_baseline,
    sha256_file
)


OUTPUT_BASELINE = (
    ROOT / "reports" / "pipeline_output_baseline.json"
)

SEED_REPORT = (
    ROOT / "reports" / "seed_provenance.json"
)


def read_json(path):
    if not path.is_file():
        raise RuntimeError(f"Missing required file: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def verify_inputs():

    saved = read_json(BASELINE_PATH)
    current = build_baseline()

    if saved != current:
        raise RuntimeError(
            "Frozen input baseline has changed"
        )

    provenance = read_json(SEED_REPORT)

    if provenance["source_run_id"] != current["run_id"]:
        raise RuntimeError("Seed provenance run mismatch")

    if (
        provenance["input_fingerprint_sha256"]
        != current["fingerprint_sha256"]
    ):
        raise RuntimeError(
            "Seed provenance input fingerprint mismatch"
        )

    # Check that the six generator source files
    # still match their recorded hashes.

    for relative_path, expected_hash in (
        provenance["generator_source_sha256"].items()
    ):
        source_path = ROOT.parent / relative_path

        if not source_path.is_file():
            raise RuntimeError(
                f"Generator source missing: {relative_path}"
            )

        if sha256_file(source_path) != expected_hash:
            raise RuntimeError(
                f"Generator source changed: {relative_path}"
            )

    return current


def build_output_snapshot():

    inputs = verify_inputs()

    run_id = inputs["run_id"]
    folder = f"run_id={run_id}"

    layers = [
        "raw",
        "processed",
        "analytics",
        "parquet"
    ]

    records = []
    layer_counts = {}

    for layer in layers:

        directory = ROOT / "data" / layer / folder

        if not directory.is_dir():
            raise RuntimeError(
                f"Missing output layer: {directory}"
            )

        files = sorted(
            path
            for path in directory.rglob("*")
            if path.is_file()
        )

        if not files:
            raise RuntimeError(
                f"Empty output layer: {directory}"
            )

        layer_counts[layer] = len(files)

        for path in files:
            records.append({
                "path": path.relative_to(ROOT).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path)
            })

    records.sort(key=lambda row: row["path"])

    parquet_count = sum(
        row["path"].endswith(".parquet")
        for row in records
    )

    if parquet_count != 366:
        raise RuntimeError(
            f"Expected 366 Parquet files, "
            f"found {parquet_count}"
        )

    snapshot = {
        "version": 1,
        "run_id": run_id,
        "input_fingerprint_sha256":
            inputs["fingerprint_sha256"],
        "layer_file_counts": layer_counts,
        "parquet_file_count": parquet_count,
        "total_file_count": len(records),
        "files": records
    }

    canonical = json.dumps(
        snapshot,
        sort_keys=True,
        separators=(",", ":")
    ).encode("utf-8")

    snapshot["output_fingerprint_sha256"] = (
        hashlib.sha256(canonical).hexdigest()
    )

    return snapshot


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--capture",
        action="store_true"
    )

    parser.add_argument(
        "--verify",
        action="store_true"
    )

    args = parser.parse_args()

    if args.capture == args.verify:
        parser.error(
            "Specify exactly one of --capture or --verify"
        )

    print("=" * 70)
    print("PHASE 8 - OUTPUT REPRODUCIBILITY")
    print("=" * 70)

    snapshot = build_output_snapshot()

    OUTPUT_BASELINE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    if args.capture:

        if OUTPUT_BASELINE.exists():

            saved = read_json(OUTPUT_BASELINE)

            if saved != snapshot:
                raise RuntimeError(
                    "Existing output baseline differs. "
                    "Original baseline preserved."
                )

            status = "MATCHED"

        else:

            with OUTPUT_BASELINE.open(
                "x",
                encoding="utf-8"
            ) as file:

                json.dump(
                    snapshot,
                    file,
                    indent=2,
                    sort_keys=True
                )

            status = "CREATED"

    else:

        saved = read_json(OUTPUT_BASELINE)

        if saved != snapshot:
            saved_files = {
                row["path"]: row
                for row in saved["files"]
            }

            current_files = {
                row["path"]: row
                for row in snapshot["files"]
            }

            differences = sorted(
                path
                for path in (
                    set(saved_files) | set(current_files)
                )
                if saved_files.get(path)
                != current_files.get(path)
            )

            raise RuntimeError(
                "OUTPUT REPRODUCIBILITY FAILED. "
                f"Differing files: {differences[:10]}. "
                f"Total differences: {len(differences)}"
            )

        status = "MATCHED"

    print(f"Source run: {snapshot['run_id']}")
    print("Input baseline: MATCHED")
    print("Generator source hashes: MATCHED")

    print("\nOutput layers:")

    for layer, count in (
        snapshot["layer_file_counts"].items()
    ):
        print(f"  {layer}: {count} files")

    print(
        f"\nParquet files: "
        f"{snapshot['parquet_file_count']}"
    )

    print(
        f"Total tracked files: "
        f"{snapshot['total_file_count']}"
    )

    print(f"Output baseline status: {status}")

    print(
        "Output fingerprint: "
        f"{snapshot['output_fingerprint_sha256']}"
    )

    print(f"Baseline file: {OUTPUT_BASELINE}")

    print()
    print("OUTPUT REPRODUCIBILITY CHECK PASSED.")


if __name__ == "__main__":
    main()
