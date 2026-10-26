
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app

from src.services.dataset_catalog_service import (
    DatasetNotReadyError,
)

from src.services.dataset_download_service import (
    resolve_dataset_download,
)


# =====================================================
# PHASE 9.7.4B - DATASET DOWNLOAD API TEST
# =====================================================

RUN_ID = (
    "api_run_ebaaf56bd9b14c1d9fca1af532387316"
)

BASE_URL = f"/api/v1/runs/{RUN_ID}/datasets"


def test_dataset_download_endpoint():

    print("=" * 70)
    print("PHASE 9 - HTTP DATASET DOWNLOAD ENDPOINT")
    print("=" * 70)

    client = TestClient(app)

    # ==========================================
    # TEST 1 - DOWNLOAD APPROVED FILE FORMATS
    # ==========================================

    samples = {
        "customers.csv": "text/csv",
        "events.jsonl": "application/x-ndjson",
        "simulation_manifest.json": "application/json",
        "analytics__customer_analytics.csv": "text/csv",
    }

    for dataset_id, expected_type in samples.items():

        response = client.get(
            f"{BASE_URL}/{dataset_id}"
        )

        assert response.status_code == 200, (
            response.text
        )

        expected = resolve_dataset_download(
            RUN_ID,
            dataset_id,
        )

        # Verify exact file content.
        assert response.content == (
            expected["file_path"].read_bytes()
        )

        # Verify format.
        assert response.headers[
            "content-type"
        ].startswith(expected_type)

        # Verify file download header.
        disposition = response.headers[
            "content-disposition"
        ]

        assert "attachment" in disposition
        assert expected["filename"] in disposition

        assert int(
            response.headers["content-length"]
        ) == expected["size_bytes"]

        print(f"{dataset_id}: HTTP 200 (PASS)")

    print("Downloaded bytes match source files: PASS")
    print("Download headers verified: PASS")

    # ==========================================
    # TEST 2 - INVALID DATASET IDENTIFIER
    # ==========================================

    invalid = client.get(
        f"{BASE_URL}/INVALID_FILE.csv"
    )

    assert invalid.status_code == 422

    print("Invalid dataset ID -> HTTP 422: PASS")

    # ==========================================
    # TEST 3 - UNREGISTERED DATASET
    # ==========================================

    unknown = client.get(
        f"{BASE_URL}/secrets.csv"
    )

    assert unknown.status_code == 404

    print("Unregistered dataset -> HTTP 404: PASS")

    # ==========================================
    # TEST 4 - INVALID RUN ID
    # ==========================================

    invalid_run = client.get(
        "/api/v1/runs/invalid-run-id/"
        "datasets/customers.csv"
    )

    assert invalid_run.status_code == 422

    print("Invalid run ID -> HTTP 422: PASS")

    # ==========================================
    # TEST 5 - UNKNOWN RUN
    # ==========================================

    unknown_run_id = "api_run_" + ("f" * 32)

    missing_run = client.get(
        f"/api/v1/runs/{unknown_run_id}/"
        "datasets/customers.csv"
    )

    assert missing_run.status_code == 404

    print("Unknown run -> HTTP 404: PASS")

    # ==========================================
    # TEST 6 - INCOMPLETE RUN
    # ==========================================

    with patch(
        "src.api.main.resolve_dataset_download",
        side_effect=DatasetNotReadyError(
            "Simulation still running"
        ),
    ):

        pending = client.get(
            f"{BASE_URL}/customers.csv"
        )

        assert pending.status_code == 409

    print("Incomplete run -> HTTP 409: PASS")

    # ==========================================
    # TEST 7 - INTERNAL FILE FAILURE
    # ==========================================

    with patch(
        "src.api.main.resolve_dataset_download",
        side_effect=RuntimeError(
            "PRIVATE_INTERNAL_PATH"
        ),
    ):

        failed = client.get(
            f"{BASE_URL}/customers.csv"
        )

        assert failed.status_code == 500

        assert "PRIVATE_INTERNAL_PATH" not in (
            str(failed.json())
        )

    print("Internal file failure -> HTTP 500: PASS")
    print("Internal error details hidden: PASS")

    # ==========================================
    # TEST 8 - OPENAPI REGISTRATION
    # ==========================================

    schema = client.get("/openapi.json").json()

    path = (
        "/api/v1/runs/{run_id}/datasets/"
        "{dataset_id}"
    )

    assert "get" in schema["paths"][path]

    print("Download endpoint in OpenAPI: PASS")

    print()
    print("Real dataset bytes read: YES")
    print("Files written or modified: NO")
    print("Generator execution: NO")

    print()
    print("HTTP DATASET DOWNLOAD ENDPOINT TEST PASSED.")


if __name__ == "__main__":
    test_dataset_download_endpoint()
