
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app

from src.services.dataset_catalog_service import (
    DatasetNotReadyError,
)


# =====================================================
# PHASE 9.7.3 - DATASET CATALOG API TEST
# =====================================================

RUN_ID = "api_run_ebaaf56bd9b14c1d9fca1af532387316"

BASE_URL = "/api/v1/runs"


def test_dataset_catalog_endpoint():

    print("=" * 70)
    print("PHASE 9 - DATASET CATALOG API ENDPOINT")
    print("=" * 70)

    client = TestClient(app)

    # ==========================================
    # TEST 1 - REAL COMPLETED RUN
    # ==========================================

    response = client.get(
        f"{BASE_URL}/{RUN_ID}/datasets"
    )

    assert response.status_code == 200

    print("Completed run -> HTTP 200: PASS")

    catalog = response.json()

    assert catalog["run_id"] == RUN_ID
    assert catalog["dataset_count"] == 24
    assert len(catalog["datasets"]) == 24

    print("24 dataset entries returned: PASS")

    datasets = catalog["datasets"]

    # ==========================================
    # TEST 2 - CATEGORY DISTRIBUTION
    # ==========================================

    expected_counts = {
        "source": 12,
        "analytics": 8,
        "metadata": 4,
    }

    for category, expected in expected_counts.items():

        actual = sum(
            item["category"] == category
            for item in datasets
        )

        assert actual == expected

        print(
            f"{category.title()} category: "
            f"{actual} (PASS)"
        )

    # ==========================================
    # TEST 3 - UNIQUE DATASET IDS
    # ==========================================

    identifiers = [
        item["dataset_id"]
        for item in datasets
    ]

    assert len(identifiers) == len(set(identifiers))

    print("Unique dataset identifiers: PASS")

    # ==========================================
    # TEST 4 - NO ABSOLUTE PATHS
    # ==========================================

    assert all(
        "\\" not in item["dataset_id"]
        and "/" not in item["dataset_id"]
        and ":" not in item["dataset_id"]
        for item in datasets
    )

    assert all(
        set(item.keys()) == {
            "dataset_id",
            "name",
            "category",
            "format",
            "size_bytes",
        }
        for item in datasets
    )

    print("Internal filesystem paths hidden: PASS")

    # ==========================================
    # TEST 5 - INVALID RUN ID
    # ==========================================

    invalid = client.get(
        f"{BASE_URL}/invalid-run-id/datasets"
    )

    assert invalid.status_code == 422

    print("Invalid run ID -> HTTP 422: PASS")

    # ==========================================
    # TEST 6 - UNKNOWN RUN
    # ==========================================

    unknown_id = "api_run_" + ("f" * 32)

    unknown = client.get(
        f"{BASE_URL}/{unknown_id}/datasets"
    )

    assert unknown.status_code == 404

    print("Unknown run -> HTTP 404: PASS")

    # ==========================================
    # TEST 7 - INCOMPLETE SIMULATION
    # ==========================================

    with patch(
        "src.api.main.list_run_datasets",
        side_effect=DatasetNotReadyError(
            "Run not completed"
        ),
    ):

        incomplete = client.get(
            f"{BASE_URL}/{RUN_ID}/datasets"
        )

        assert incomplete.status_code == 409

    print("Incomplete run -> HTTP 409: PASS")

    # ==========================================
    # TEST 8 - INTERNAL CATALOG FAILURE
    # ==========================================

    with patch(
        "src.api.main.list_run_datasets",
        side_effect=RuntimeError(
            "Simulated catalog failure"
        ),
    ):

        failed = client.get(
            f"{BASE_URL}/{RUN_ID}/datasets"
        )

        assert failed.status_code == 500

        assert "Simulated catalog failure" not in (
            str(failed.json())
        )

    print("Internal catalog error -> HTTP 500: PASS")
    print("Internal error details hidden: PASS")

    # ==========================================
    # TEST 9 - OPENAPI REGISTRATION
    # ==========================================

    schema = client.get("/openapi.json").json()

    assert (
        "get"
        in schema["paths"][
            "/api/v1/runs/{run_id}/datasets"
        ]
    )

    print("Endpoint registered in OpenAPI: PASS")

    print()
    print("Actual generator execution: NO")
    print("Dataset files modified: NO")
    print("Dataset downloads enabled: NO")

    print()
    print("DATASET CATALOG API ENDPOINT TEST PASSED.")


if __name__ == "__main__":

    test_dataset_catalog_endpoint()
