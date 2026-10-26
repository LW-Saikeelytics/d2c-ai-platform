
import os

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app

from src.services.execution_lock import (
    SimulationBusyError,
)


ENDPOINT = "/api/v1/runs"

VALID_REQUEST = {
    "days": 7,
    "customers": 100,
    "scenario": "baseline",
    "seed": 42,
}

FAKE_RUN_ID = "api_run_" + ("a" * 32)


def test_simulation_start_endpoint():

    print("=" * 70)
    print("PHASE 9 - HTTP SIMULATION START ENDPOINT")
    print("=" * 70)

    client = TestClient(app)

    # ==========================================
    # TEST 1 - EXECUTION DISABLED BY DEFAULT
    # ==========================================

    with (
        patch.dict(
            os.environ,
            {"M14_ENABLE_SIMULATION_START": "0"},
        ),
        patch(
            "src.api.main.run_managed_simulation"
        ) as executor,
    ):

        response = client.post(
            ENDPOINT,
            json=VALID_REQUEST,
        )

        assert response.status_code == 503

        executor.assert_not_called()

    print("Execution disabled -> HTTP 503: PASS")
    print("Disabled request launches nothing: PASS")

    # ==========================================
    # TEST 2 - MOCKED SUCCESSFUL EXECUTION
    # ==========================================

    fake_record = {
        "run_id": FAKE_RUN_ID,
        "status": "COMPLETED",
        "scenario": "baseline",
        "days": 7,
        "customers": 100,
        "created_at": "2026-10-25T09:00:00+00:00",
        "started_at": "2026-10-25T09:00:01+00:00",
        "finished_at": "2026-10-25T09:00:02+00:00",
        "exit_code": 0,
        "generated_run_directory": "PRIVATE_TEST_PATH",
        "error": None,
    }

    with (
        patch.dict(
            os.environ,
            {"M14_ENABLE_SIMULATION_START": "1"},
        ),
        patch(
            "src.api.main.run_managed_simulation",
            return_value=(fake_record, None),
        ) as executor,
    ):

        response = client.post(
            ENDPOINT,
            json=VALID_REQUEST,
        )

        assert response.status_code == 201

        payload = response.json()

        assert payload["run_id"] == FAKE_RUN_ID
        assert payload["status"] == "COMPLETED"
        assert payload["days"] == 7
        assert payload["customers"] == 100

        assert response.headers["location"] == (
            f"/api/v1/runs/{FAKE_RUN_ID}"
        )

        assert "generated_run_directory" not in payload
        assert "error" not in payload

        executor.assert_called_once()

        submitted_config = executor.call_args.args[0]

        assert submitted_config.model_dump() == (
            VALID_REQUEST
        )

    print("Valid request -> HTTP 201: PASS")
    print("Configuration forwarded correctly: PASS")
    print("Run status returned: PASS")
    print("Location header generated: PASS")
    print("Internal execution details hidden: PASS")

    # ==========================================
    # TEST 3 - CONCURRENT EXECUTION REJECTION
    # ==========================================

    with (
        patch.dict(
            os.environ,
            {"M14_ENABLE_SIMULATION_START": "1"},
        ),
        patch(
            "src.api.main.run_managed_simulation",
            side_effect=SimulationBusyError(
                "Another simulation is active"
            ),
        ),
    ):

        response = client.post(
            ENDPOINT,
            json=VALID_REQUEST,
        )

        assert response.status_code == 409

    print("Concurrent execution -> HTTP 409: PASS")

    # ==========================================
    # TEST 4 - INVALID CONFIGURATION
    # ==========================================

    invalid_request = {
        **VALID_REQUEST,
        "days": 31,
    }

    with (
        patch.dict(
            os.environ,
            {"M14_ENABLE_SIMULATION_START": "1"},
        ),
        patch(
            "src.api.main.run_managed_simulation"
        ) as executor,
    ):

        response = client.post(
            ENDPOINT,
            json=invalid_request,
        )

        assert response.status_code == 422

        executor.assert_not_called()

    print("Invalid execution request -> HTTP 422: PASS")
    print("Invalid request launches nothing: PASS")

    # ==========================================
    # TEST 5 - OPENAPI DOCUMENTATION
    # ==========================================

    response = client.get("/openapi.json")

    assert response.status_code == 200

    paths = response.json()["paths"]

    assert "post" in paths[ENDPOINT]

    print("Simulation endpoint in OpenAPI: PASS")

    print()
    print("Actual generator execution performed: NO")
    print("Real workspace reservations: 0")
    print("Existing run records modified: NO")

    print()
    print("HTTP SIMULATION START ENDPOINT TEST PASSED.")


if __name__ == "__main__":

    test_simulation_start_endpoint()
