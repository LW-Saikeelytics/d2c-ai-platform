
import io
import json
import os

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app

from src.observability.production_logger import (
    ProductionLogger,
)

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


def test_simulation_exception_logging():

    client = TestClient(app)

    secret = "PRIVATE_PASSWORD_DO_NOT_LOG"

    cases = [
        (
            "busy_simulation",
            SimulationBusyError(secret),
            409,
            "WARNING",
            "simulation_execution_busy",
        ),
        (
            "runtime_failure",
            RuntimeError(secret),
            503,
            "ERROR",
            "simulation_execution_failed",
        ),
        (
            "os_failure",
            OSError(secret),
            503,
            "ERROR",
            "simulation_execution_failed",
        ),
    ]

    for (
        name,
        exception,
        expected_status,
        expected_level,
        expected_event,
    ) in cases:

        output = io.StringIO()

        logger = ProductionLogger(
            component="api",
            stream=output,
        )

        environment = {
            "M14_ENV": "development",
            "M14_ENABLE_SIMULATION_START": "1",
        }

        with (
            patch.dict(os.environ, environment),
            patch(
                "src.api.main.run_managed_simulation",
                side_effect=exception,
            ) as executor,
            patch(
                "src.api.main.api_logger",
                logger,
            ),
        ):

            response = client.post(
                ENDPOINT,
                json=VALID_REQUEST,
            )

            assert response.status_code == expected_status

            executor.assert_called_once()

        records = [
            json.loads(line)
            for line in output.getvalue().splitlines()
            if line.strip()
        ]

        assert len(records) == 1

        record = records[0]

        assert record["level"] == expected_level
        assert record["event"] == expected_event
        assert record["component"] == "api"
        assert record["error_type"] == (
            type(exception).__name__
        )

        assert record["execution_id"] is None

        # Ensure neither the API response nor diagnostic
        # output contains the sensitive exception message.

        assert secret not in response.text
        assert secret not in output.getvalue()

        if expected_status == 409:
            assert response.json()["detail"] == (
                "Another simulation is already active"
            )
        else:
            assert response.json()["detail"] == (
                "Simulation execution unavailable; "
                "inspect the local runtime logs"
            )

        print(f"{name}: PASS")

    print()
    print("Structured failure events: 3")
    print("Original HTTP error responses preserved: PASS")
    print("Sensitive exception messages excluded: PASS")
    print("Actual simulation execution: NO")
    print("Existing simulation data modified: NO")
    print()
    print("SIMULATION EXCEPTION LOGGING TEST PASSED.")


if __name__ == "__main__":
    test_simulation_exception_logging()
