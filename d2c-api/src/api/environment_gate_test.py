
import os

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app


ENDPOINT = "/api/v1/runs"

VALID_REQUEST = {
    "days": 7,
    "customers": 100,
    "scenario": "baseline",
    "seed": 42,
}


def test_environment_gate():

    client = TestClient(app)

    blocked_cases = [
        (
            "development_disabled",
            {
                "M14_ENV": "development",
                "M14_ENABLE_SIMULATION_START": "0",
            },
        ),
        (
            "testing_disabled",
            {
                "M14_ENV": "testing",
                "M14_ENABLE_SIMULATION_START": "0",
            },
        ),
        (
            "production_disabled",
            {
                "M14_ENV": "production",
                "M14_ENABLE_SIMULATION_START": "0",
            },
        ),
        (
            "production_execution_blocked",
            {
                "M14_ENV": "production",
                "M14_ENABLE_SIMULATION_START": "1",
            },
        ),
        (
            "invalid_environment_blocked",
            {
                "M14_ENV": "unknown",
                "M14_ENABLE_SIMULATION_START": "1",
            },
        ),
        (
            "invalid_execution_flag_blocked",
            {
                "M14_ENV": "development",
                "M14_ENABLE_SIMULATION_START": "yes",
            },
        ),
    ]

    for name, environment in blocked_cases:

        with (
            patch.dict(os.environ, environment),
            patch(
                "src.api.main.run_managed_simulation"
            ) as executor,
        ):

            response = client.post(
                ENDPOINT,
                json=VALID_REQUEST,
            )

            assert response.status_code == 503, (
                f"{name}: expected 503, "
                f"got {response.status_code}"
            )

            assert response.json()["detail"] == (
                "Simulation execution is disabled"
            )

            executor.assert_not_called()

            print(f"{name}: PASS")

    print()
    print("Actual simulation execution: NO")
    print("Production execution blocked: PASS")
    print("ENVIRONMENT GATE TEST PASSED.")


if __name__ == "__main__":
    test_environment_gate()