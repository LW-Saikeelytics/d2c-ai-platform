
import json

from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError
)


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CONFIG_PATH = (
    ROOT / "config" / "development_simulation.json"
)


# =====================================================
# PHASE 9.1 - SIMULATION CONFIGURATION CONTRACT
# =====================================================

class SimulationConfig(BaseModel):

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    days: int = Field(
        default=90,
        gt=0,
        strict=True
    )

    customers: int = Field(
        default=10000,
        gt=0,
        strict=True
    )

    scenario: str = Field(
        default="baseline",
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$"
    )

    # The existing generator currently uses
    # a fixed production seed of 42.
    #
    # Do not pretend arbitrary seeds are
    # supported until the engine is updated.

    seed: Literal[42] = 42


# =====================================================
# LOAD CONFIGURATION FROM JSON
# =====================================================

def load_simulation_config(
    path=DEFAULT_CONFIG_PATH
):

    path = Path(path)

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    return SimulationConfig.model_validate(data)


# =====================================================
# TRANSLATE CONFIG TO EXISTING RUNNER ARGUMENTS
# =====================================================

def build_runner_arguments(config):

    return [
        "--days",
        str(config.days),

        "--customers",
        str(config.customers),

        "--scenario",
        config.scenario
    ]


# =====================================================
# SELF-TEST
# =====================================================

def test_configuration():

    config = load_simulation_config()

    assert config.days == 7
    assert config.customers == 100
    assert config.scenario == "baseline"
    assert config.seed == 42

    print("JSON configuration loading: PASS")
    print("Configuration field validation: PASS")

    expected_arguments = [
        "--days", "7",
        "--customers", "100",
        "--scenario", "baseline"
    ]

    actual_arguments = build_runner_arguments(
        config
    )

    assert actual_arguments == expected_arguments

    print("Simulation CLI argument mapping: PASS")

    invalid_cases = {
        "zero_days": {"days": 0},
        "negative_customers": {"customers": -5},
        "invalid_seed": {"seed": 43},
        "unsafe_scenario": {"scenario": "../invalid"},
        "unknown_parameter": {"unexpected": 123},
        "string_days": {"days": "7"}
    }

    for name, override in invalid_cases.items():

        test_data = {
            **config.model_dump(),
            **override
        }

        try:
            SimulationConfig.model_validate(test_data)

        except ValidationError:
            print(f"{name}: REJECTED (PASS)")

        else:
            raise AssertionError(
                f"Invalid configuration accepted: {name}"
            )

    print()
    print("Validated development configuration:")
    print(
        json.dumps(
            config.model_dump(),
            indent=2
        )
    )

    print()
    print(
        "Runner arguments:",
        " ".join(actual_arguments)
    )

    print()
    print(
        "SIMULATION CONFIGURATION TEST PASSED."
    )


if __name__ == "__main__":

    print("=" * 70)
    print("PHASE 9 - SIMULATION CONFIGURATION VALIDATION")
    print("=" * 70)

    test_configuration()
