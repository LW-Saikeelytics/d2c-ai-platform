
import json
import re

from pathlib import Path

from .simulation_config import (
    ROOT,
    SimulationConfig,
    load_simulation_config,
    build_runner_arguments
)


SCENARIO_FILE = (
    ROOT.parent
    / "d2c-synthetic-data"
    / "config"
    / "simulation_scenarios.json"
)


# =====================================================
# READ AND VALIDATE SCENARIO REGISTRY
# =====================================================

def load_scenario_registry(path=SCENARIO_FILE):

    path = Path(path)

    if not path.is_file():
        raise FileNotFoundError(
            f"Scenario configuration missing: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        registry = json.load(file)

    if not isinstance(registry, dict):
        raise ValueError(
            "Scenario registry must be a JSON object"
        )

    scenarios = registry.get("scenarios")
    default = registry.get("default_scenario")

    if not isinstance(scenarios, dict) or not scenarios:
        raise ValueError(
            "Scenario registry must contain scenarios"
        )

    if default not in scenarios:
        raise ValueError(
            "Default scenario is not registered"
        )

    for name, definition in scenarios.items():

        if (
            not isinstance(name, str)
            or len(name) > 64
            or not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9_-]*",
                name
            )
        ):
            raise ValueError(
                f"Invalid scenario identifier: {name!r}"
            )

        if not isinstance(definition, dict):
            raise ValueError(
                f"Invalid scenario definition: {name}"
            )

        if not isinstance(
            definition.get("description"), str
        ):
            raise ValueError(
                f"Missing scenario description: {name}"
            )

        if not isinstance(
            definition.get("overrides"), dict
        ):
            raise ValueError(
                f"Invalid scenario overrides: {name}"
            )

    return registry


# =====================================================
# LIST SUPPORTED SCENARIOS
# =====================================================

def get_supported_scenarios():

    registry = load_scenario_registry()

    return {
        name: {
            "name": name,
            "description": definition["description"],
            "override_sections": sorted(
                definition["overrides"].keys()
            )
        }
        for name, definition
        in registry["scenarios"].items()
    }


# =====================================================
# VALIDATE REQUESTED SCENARIO
# =====================================================

def validate_scenario(config: SimulationConfig):

    registry = load_scenario_registry()

    scenarios = registry["scenarios"]

    if config.scenario not in scenarios:

        available = ", ".join(
            sorted(scenarios.keys())
        )

        raise ValueError(
            f"Unsupported simulation scenario: "
            f"{config.scenario}. "
            f"Available scenarios: {available}"
        )

    definition = scenarios[config.scenario]

    return {
        "name": config.scenario,
        "description": definition["description"],
        "override_sections": sorted(
            definition["overrides"].keys()
        )
    }


# =====================================================
# SELF-TEST
# =====================================================

def test_scenario_registry():

    registry = load_scenario_registry()
    supported = get_supported_scenarios()

    expected = {
        "baseline",
        "festive_peak",
        "promotion_heavy",
        "low_inventory",
        "slow_demand"
    }

    if set(supported.keys()) != expected:
        raise AssertionError(
            "Supported scenario inventory changed"
        )

    print("Scenario registry loading: PASS")
    print("Five supported scenarios verified: PASS")

    config = load_simulation_config()

    default = registry["default_scenario"]

    if default != "baseline":
        raise AssertionError(
            "Unexpected default scenario"
        )

    print("Default scenario validation: PASS")

    # Test each registered scenario using the
    # existing Phase 9 configuration contract.

    for name in sorted(supported):

        candidate = SimulationConfig.model_validate({
            **config.model_dump(),
            "scenario": name
        })

        result = validate_scenario(candidate)

        if result["name"] != name:
            raise AssertionError(
                f"Scenario mismatch: {name}"
            )

        arguments = build_runner_arguments(
            candidate
        )

        if arguments[-1] != name:
            raise AssertionError(
                f"CLI scenario mapping mismatch: {name}"
            )

        print(f"{name}: ACCEPTED (PASS)")

    # An identifier can be syntactically safe
    # but still not exist in the registry.

    unknown = SimulationConfig.model_validate({
        **config.model_dump(),
        "scenario": "not_a_scenario"
    })

    try:
        validate_scenario(unknown)

    except ValueError:
        print("Unknown scenario: REJECTED (PASS)")

    else:
        raise AssertionError(
            "Unknown scenario was accepted"
        )

    print()
    print("Available scenarios:")

    for name, details in sorted(supported.items()):
        print(
            f"  {name}: {details['description']}"
        )

    print()
    print("Generator execution performed: NO")

    print()
    print(
        "SCENARIO REGISTRY VALIDATION PASSED."
    )


if __name__ == "__main__":

    print("=" * 70)
    print("PHASE 9 - SCENARIO REGISTRY VALIDATION")
    print("=" * 70)

    test_scenario_registry()