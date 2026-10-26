
from pydantic import ValidationError

from src.api.simulation_start_request import (
    SimulationStartRequest,
    MAX_DAYS,
    MAX_CUSTOMERS,
    MAX_WORK_UNITS,
)

from src.config.simulation_config import (
    build_runner_arguments,
)


def test_simulation_execution_limits():

    print("=" * 70)
    print("PHASE 9 - API SIMULATION EXECUTION LIMITS")
    print("=" * 70)

    valid_config = {
        "days": 7,
        "customers": 100,
        "scenario": "baseline",
        "seed": 42,
    }

    # ==========================================
    # TEST 1 - VALID REQUEST
    # ==========================================

    request = SimulationStartRequest.model_validate(
        valid_config
    )

    assert request.days == 7
    assert request.customers == 100

    print("Valid simulation request: ACCEPTED (PASS)")

    # ==========================================
    # TEST 2 - EXISTING GENERATOR COMPATIBILITY
    # ==========================================

    config = request.to_simulation_config()

    arguments = build_runner_arguments(config)

    assert arguments == [
        "--days", "7",
        "--customers", "100",
        "--scenario", "baseline",
    ]

    print("Generator configuration compatibility: PASS")

    # ==========================================
    # TEST 3 - SAFE UPPER BOUNDARIES
    # ==========================================

    upper = SimulationStartRequest(
        days=7,
        customers=1000,
        scenario="baseline",
        seed=42,
    )

    assert upper.days * upper.customers == MAX_WORK_UNITS

    print("Maximum permitted workload: ACCEPTED (PASS)")

    assert MAX_DAYS == 30
    assert MAX_CUSTOMERS == 1000

    print("Individual execution limits configured: PASS")

    # ==========================================
    # TEST 4 - ALL SUPPORTED SCENARIOS
    # ==========================================

    supported = [
        "baseline",
        "festive_peak",
        "promotion_heavy",
        "low_inventory",
        "slow_demand",
    ]

    for scenario in supported:

        candidate = SimulationStartRequest(
            days=7,
            customers=100,
            scenario=scenario,
            seed=42,
        )

        assert candidate.scenario == scenario

    print("Five supported scenarios: ACCEPTED (PASS)")

    # ==========================================
    # TEST 5 - INVALID REQUESTS
    # ==========================================

    invalid_cases = {
        "Zero days": {"days": 0},
        "Too many days": {"days": 31},
        "Zero customers": {"customers": 0},
        "Too many customers": {"customers": 1001},
        "Excessive combined workload": {
            "days": 30,
            "customers": 1000,
        },
        "String days": {"days": "7"},
        "Boolean customers": {"customers": True},
        "Unsupported seed": {"seed": 99},
        "Unknown scenario": {
            "scenario": "unknown_scenario",
        },
        "Unsafe scenario": {
            "scenario": "../unsafe",
        },
        "Unexpected field": {
            "admin_override": True,
        },
    }

    for label, changes in invalid_cases.items():

        candidate = {
            **valid_config,
            **changes,
        }

        try:

            SimulationStartRequest.model_validate(
                candidate
            )

        except ValidationError:

            print(f"{label}: REJECTED (PASS)")

        else:

            raise AssertionError(
                f"Invalid request accepted: {label}"
            )

    # ==========================================
    # TEST 6 - REQUIRED PARAMETERS
    # ==========================================

    incomplete = valid_config.copy()
    incomplete.pop("customers")

    try:

        SimulationStartRequest.model_validate(
            incomplete
        )

    except ValidationError:

        print("Missing required parameter: REJECTED (PASS)")

    else:

        raise AssertionError(
            "Missing required field was accepted"
        )

    print()
    print("API limits:")
    print(f"Maximum days: {MAX_DAYS}")
    print(f"Maximum customers: {MAX_CUSTOMERS}")
    print(f"Maximum work units: {MAX_WORK_UNITS}")

    print()
    print("Generator execution performed: NO")
    print("Simulation workspace created: NO")

    print()
    print("API SIMULATION EXECUTION LIMITS PASSED.")


if __name__ == "__main__":

    test_simulation_execution_limits()