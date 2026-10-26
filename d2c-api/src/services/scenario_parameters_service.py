
import math
import re

from copy import deepcopy

from src.config.scenario_registry import (
    load_scenario_registry,
)


# =====================================================
# PHASE 9.10.2 - SCENARIO PARAMETERS SERVICE
# =====================================================

SCENARIO_NAME_PATTERN = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}"
)


class ScenarioNotFoundError(LookupError):
    """Requested scenario is not registered."""


# =====================================================
# COUNT CONFIGURED OVERRIDE PARAMETERS
# =====================================================

def count_override_parameters(value):

    if isinstance(value, dict):

        total = 0

        for key, nested_value in value.items():

            if not isinstance(key, str) or not key:
                raise ValueError(
                    "Invalid scenario parameter key"
                )

            total += count_override_parameters(
                nested_value
            )

        return total

    if isinstance(value, list):

        return sum(
            count_override_parameters(item)
            for item in value
        )

    if type(value) not in (
        str,
        int,
        float,
        bool,
    ):
        raise ValueError(
            "Unsupported scenario parameter value"
        )

    if type(value) is float and not math.isfinite(value):
        raise ValueError(
            "Non-finite scenario parameter"
        )

    return 1


# =====================================================
# RETRIEVE ONE SCENARIO'S ACTUAL PARAMETERS
# =====================================================

def get_scenario_parameters(scenario_name):

    # ---------------------------------------------
    # VALIDATE SCENARIO IDENTIFIER
    # ---------------------------------------------

    if (
        not isinstance(scenario_name, str)
        or not SCENARIO_NAME_PATTERN.fullmatch(
            scenario_name
        )
    ):
        raise ValueError(
            "Invalid scenario identifier"
        )

    # ---------------------------------------------
    # READ ORIGINAL PHASE 6 REGISTRY
    # ---------------------------------------------

    registry = load_scenario_registry()

    scenarios = registry["scenarios"]

    if scenario_name not in scenarios:

        raise ScenarioNotFoundError(
            "Simulation scenario not found"
        )

    definition = scenarios[scenario_name]

    # Use a copy so callers cannot mutate
    # the loaded scenario definition.
    overrides = deepcopy(
        definition["overrides"]
    )

    parameter_count = count_override_parameters(
        overrides
    )

    # ---------------------------------------------
    # BUILD PUBLIC SCENARIO DETAILS
    # ---------------------------------------------

    return {
        "name": scenario_name,
        "description": definition["description"],
        "is_default": (
            scenario_name
            == registry["default_scenario"]
        ),
        "override_sections": sorted(
            overrides.keys()
        ),
        "parameter_count": parameter_count,
        "overrides": overrides,
    }
