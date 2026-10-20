
import hashlib
import json

from pathlib import Path

from .pipeline_logger import ROOT


BASELINE_PATH = (
    ROOT / "reports" / "reproducibility_baseline.json"
)


def sha256_file(path):
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b""
        ):
            digest.update(chunk)

    return digest.hexdigest()


def build_baseline():

    config_path = (
        ROOT / "config" / "platform_config.json"
    )

    with config_path.open(
        "r", encoding="utf-8"
    ) as file:
        config = json.load(file)

    run_id = config["source"]["run_id"]

    raw_dir = (
        ROOT / "data" / "raw" / f"run_id={run_id}"
    )

    if not raw_dir.is_dir():
        raise RuntimeError(
            f"Raw source directory missing: {raw_dir}"
        )

    raw_manifest = raw_dir / "_raw_manifest.json"

    if not raw_manifest.is_file():
        raise RuntimeError(
            "Verified raw manifest is missing"
        )

    with raw_manifest.open(
        "r", encoding="utf-8"
    ) as file:
        metadata = json.load(file)

    if metadata.get("run_id") != run_id:
        raise RuntimeError(
            "Raw manifest run ID mismatch"
        )

    raw_files = sorted(
        path
        for path in raw_dir.rglob("*")
        if path.is_file()
        and path != raw_manifest
    )

    if len(raw_files) != 25:
        raise RuntimeError(
            f"Expected 25 raw source files, "
            f"found {len(raw_files)}"
        )

    metadata_files = [
        config_path,
        ROOT / "config" / "database_config.json",
        ROOT / "schemas" / "canonical_schema.json",
        raw_manifest
    ]

    input_files = metadata_files + raw_files

    entries = []

    for path in input_files:

        if not path.is_file():
            raise RuntimeError(
                f"Input file missing: {path}"
            )

        entries.append({
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(path)
        })

    entries.sort(key=lambda item: item["path"])

    baseline = {
        "version": 1,
        "run_id": run_id,
        "raw_source_file_count": len(raw_files),
        "input_file_count": len(entries),
        "inputs": entries
    }

    canonical = json.dumps(
        baseline,
        sort_keys=True,
        separators=(",", ":")
    ).encode("utf-8")

    baseline["fingerprint_sha256"] = (
        hashlib.sha256(canonical).hexdigest()
    )

    return baseline


def main():

    print("=" * 70)
    print("PHASE 8 - REPRODUCIBILITY BASELINE")
    print("=" * 70)

    baseline = build_baseline()

    BASELINE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    if BASELINE_PATH.exists():

        with BASELINE_PATH.open(
            "r", encoding="utf-8"
        ) as file:
            previous = json.load(file)

        if previous != baseline:
            raise RuntimeError(
                "REPRODUCIBILITY CHECK FAILED: "
                "tracked inputs differ from the saved "
                "baseline. Original baseline preserved."
            )

        status = "MATCHED"

    else:

        with BASELINE_PATH.open(
            "x", encoding="utf-8"
        ) as file:
            json.dump(
                baseline,
                file,
                indent=2,
                sort_keys=True
            )

        status = "CREATED"

    print(f"Run ID: {baseline['run_id']}")

    print(
        f"Raw source files: "
        f"{baseline['raw_source_file_count']}"
    )

    print(
        f"Total tracked input files: "
        f"{baseline['input_file_count']}"
    )

    print(
        f"Baseline status: {status}"
    )

    print(
        f"Fingerprint: "
        f"{baseline['fingerprint_sha256']}"
    )

    print(f"Baseline file: {BASELINE_PATH}")

    print()
    print("REPRODUCIBILITY BASELINE VALIDATION PASSED.")


if __name__ == "__main__":
    main()
