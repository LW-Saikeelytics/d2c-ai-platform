
from fastapi.testclient import TestClient

from src.api.main import app


def test_request_validation():

    client = TestClient(app)

    endpoint = "/api/v1/config/validate"

    valid_config = {
        "days": 7,
        "customers": 100,
        "scenario": "baseline",
        "seed": 42,
    }

    print("=" * 70)
    print("PHASE 9 - API REQUEST VALIDATION")
    print("=" * 70)

    # Valid configuration
    response = client.post(
        endpoint,
        json=valid_config,
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["valid"] is True
    assert payload["configuration"] == valid_config

    print("Valid configuration: ACCEPTED (PASS)")

    # Invalid configurations
    invalid_cases = {
        "Zero days": {"days": 0},
        "Negative customers": {"customers": -10},
        "String days": {"days": "7"},
        "Boolean customers": {"customers": True},
        "Unsupported seed": {"seed": 99},
        "Unknown scenario": {
            "scenario": "unknown_scenario"
        },
        "Unsafe scenario": {
            "scenario": "../unsafe"
        },
        "Extra field": {
            "unknown_parameter": 123
        },
    }

    for label, changes in invalid_cases.items():

        candidate = {
            **valid_config,
            **changes,
        }

        response = client.post(
            endpoint,
            json=candidate,
        )

        assert response.status_code == 422, (
            f"{label}: unexpected HTTP "
            f"{response.status_code}"
        )

        print(f"{label}: REJECTED (PASS)")

    # Verify simulation execution remains disabled
    response = client.post(
        "/api/v1/runs",
        json=valid_config,
    )

    assert response.status_code == 503

    print("Simulation execution endpoint: DISABLED (PASS)")

    print()
    print("Actual simulation executions: 0")
    print("No workspace reservations requested")
    print()
    print("API REQUEST VALIDATION TEST PASSED.")


if __name__ == "__main__":
    test_request_validation()