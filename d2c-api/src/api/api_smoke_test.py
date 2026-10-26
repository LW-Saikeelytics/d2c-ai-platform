
from uuid import uuid4

from fastapi.testclient import TestClient

from src.api.main import app


KNOWN_RUN_ID = (
    "api_run_71e00acdec7c445fbee437ed68795f29"
)


def test_api():

    client = TestClient(app)

    print("=" * 70)
    print("PHASE 9 - FASTAPI READ-ONLY ENDPOINT TEST")
    print("=" * 70)

    # ----------------------------------------
    # TEST 1: HEALTH
    # ----------------------------------------

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

    print("GET /health: PASS")

    # ----------------------------------------
    # TEST 2: SCENARIO REGISTRY
    # ----------------------------------------

    response = client.get("/api/v1/scenarios")

    assert response.status_code == 200

    payload = response.json()

    expected = {
        "baseline",
        "festive_peak",
        "promotion_heavy",
        "low_inventory",
        "slow_demand",
    }

    names = {
        item["name"]
        for item in payload["scenarios"]
    }

    assert names == expected
    assert payload["total"] == 5

    print("GET /api/v1/scenarios: PASS")

    # ----------------------------------------
    # TEST 3: RUN HISTORY
    # ----------------------------------------

    response = client.get("/api/v1/runs")

    assert response.status_code == 200

    payload = response.json()

    assert payload["total"] >= 2

    assert any(
        item["run_id"] == KNOWN_RUN_ID
        for item in payload["runs"]
    )

    print("GET /api/v1/runs: PASS")

    # ----------------------------------------
    # TEST 4: INDIVIDUAL RUN
    # ----------------------------------------

    response = client.get(
        f"/api/v1/runs/{KNOWN_RUN_ID}"
    )

    assert response.status_code == 200

    record = response.json()

    assert record["run_id"] == KNOWN_RUN_ID
    assert record["status"] == "COMPLETED"
    assert record["days"] == 7
    assert record["customers"] == 100
    assert record["exit_code"] == 0

    assert "generated_run_directory" not in record
    assert "error" not in record

    print("GET /api/v1/runs/{run_id}: PASS")
    print("Internal filesystem paths hidden: PASS")

    # ----------------------------------------
    # TEST 5: INVALID RUN ID
    # ----------------------------------------

    response = client.get(
        "/api/v1/runs/invalid-run-id"
    )

    assert response.status_code == 422

    print("Invalid run ID -> HTTP 422: PASS")

    # ----------------------------------------
    # TEST 6: NONEXISTENT RUN
    # ----------------------------------------

    missing_id = f"api_run_{uuid4().hex}"

    response = client.get(
        f"/api/v1/runs/{missing_id}"
    )

    assert response.status_code == 404

    print("Missing run -> HTTP 404: PASS")

    # ----------------------------------------
    # TEST 7: EXECUTION NOT EXPOSED
    # ----------------------------------------

    response = client.post(
        "/api/v1/runs",
        json={
            "days": 7,
            "customers": 100,
            "scenario": "baseline",
            "seed": 42,
        },
    )

    assert response.status_code == 503

    print("Simulation POST disabled: PASS")

    # ----------------------------------------
    # TEST 8: OPENAPI DOCUMENTATION
    # ----------------------------------------

    response = client.get("/openapi.json")

    assert response.status_code == 200

    print("OpenAPI schema generation: PASS")

    print()
    print("Recorded simulations:", payload["total"])
    print("Actual simulation execution: NO")
    print("Existing datasets modified: NO")

    print()
    print("FASTAPI READ-ONLY ENDPOINT TEST PASSED.")


if __name__ == "__main__":
    test_api()
