
from src.services.dataset_download_service import (
    DATASET_FILES,
    DatasetNotFoundError,
    resolve_dataset_download,
)


RUN_ID = (
    "api_run_ebaaf56bd9b14c1d9fca1af532387316"
)


def test_dataset_download_resolver():

    print("=" * 70)
    print("PHASE 9 - SAFE DATASET DOWNLOAD RESOLVER")
    print("=" * 70)

    assert len(DATASET_FILES) == 24

    print("Approved dataset identifiers: 24 (PASS)")

    samples = {
        "customers.csv": "text/csv",
        "events.jsonl": "application/x-ndjson",
        "simulation_manifest.json": "application/json",
        "analytics__customer_analytics.csv": "text/csv",
    }

    for dataset_id, expected_type in samples.items():

        resolved = resolve_dataset_download(
            RUN_ID,
            dataset_id,
        )

        assert resolved["dataset_id"] == dataset_id
        assert resolved["file_path"].is_file()
        assert resolved["media_type"] == expected_type
        assert resolved["size_bytes"] >= 0

        print(f"{dataset_id}: RESOLVED (PASS)")

    invalid_ids = [
        "../orders.csv",
        "analytics/../orders.csv",
        r"..\orders.csv",
        "C:\\secrets.csv",
        "customers.csv/../../secrets.csv",
        "",
    ]

    for dataset_id in invalid_ids:

        try:
            resolve_dataset_download(
                RUN_ID,
                dataset_id,
            )

        except ValueError:
            pass

        else:
            raise AssertionError(
                f"Unsafe dataset ID accepted: {dataset_id}"
            )

    print("Unsafe dataset identifiers rejected: PASS")

    try:
        resolve_dataset_download(
            RUN_ID,
            "secrets.csv",
        )

    except DatasetNotFoundError:
        print("Unregistered dataset rejected: PASS")

    else:
        raise AssertionError(
            "Unregistered dataset was accepted"
        )

    try:
        resolve_dataset_download(
            "invalid-run-id",
            "customers.csv",
        )

    except ValueError:
        print("Invalid run identifier rejected: PASS")

    else:
        raise AssertionError(
            "Invalid run ID was accepted"
        )

    print()
    print("Actual dataset downloads: NO")
    print("Filesystem modifications: NO")
    print("Generator execution: NO")

    print()
    print("SAFE DATASET DOWNLOAD RESOLVER PASSED.")


if __name__ == "__main__":
    test_dataset_download_resolver()
