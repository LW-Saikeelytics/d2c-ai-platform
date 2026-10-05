import copy
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


def load_json(filename):

    path = CONFIG_DIR / filename

    if not path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {path}"
        )

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# ==========================================================
# DEEP MERGE
# ==========================================================

def deep_merge(
    base,
    overrides
):

    result = copy.deepcopy(
        base
    )

    for key, value in overrides.items():

        if (
            isinstance(value, dict)
            and isinstance(
                result.get(key),
                dict
            )
        ):

            result[key] = deep_merge(
                result[key],
                value
            )

        else:

            result[key] = copy.deepcopy(
                value
            )

    return result


# ==========================================================
# BASE CONFIG
# ==========================================================

def load_base_config():

    return {
        "company":
            load_json(
                "company_config.json"
            ),

        "products":
            load_json(
                "product_master.json"
            ),

        "variants":
            load_json(
                "variant_master.json"
            ),

        "cities":
            load_json(
                "city_master.json"
            ),

        "warehouses":
            load_json(
                "warehouse_master.json"
            ),

        "carriers":
            load_json(
                "carrier_master.json"
            ),

        "customer_segments":
            load_json(
                "customer_segments.json"
            ),

        "channels":
            load_json(
                "channels.json"
            ),

        "payment_methods":
            load_json(
                "payment_methods.json"
            ),

        "promotions":
            load_json(
                "promotions.json"
            ),

        "support_categories":
            load_json(
                "support_categories.json"
            ),

        "return_reasons":
            load_json(
                "return_reasons.json"
            )
    }


# ==========================================================
# SCENARIO DEFINITIONS
# ==========================================================

def load_scenario_definitions():

    return load_json(
        "simulation_scenarios.json"
    )


def get_available_scenarios():

    scenario_config = (
        load_scenario_definitions()
    )

    return list(
        scenario_config.get(
            "scenarios",
            {}
        ).keys()
    )


# ==========================================================
# COMPLETE CONFIG
# ==========================================================

def load_all_config(
    scenario_name=None
):

    config = (
        load_base_config()
    )

    scenario_config = (
        load_scenario_definitions()
    )

    if scenario_name is None:

        scenario_name = (
            scenario_config.get(
                "default_scenario",
                "baseline"
            )
        )

    scenarios = (
        scenario_config.get(
            "scenarios",
            {}
        )
    )

    if scenario_name not in scenarios:

        available = ", ".join(
            sorted(
                scenarios.keys()
            )
        )

        raise ValueError(
            f"Unknown simulation scenario: "
            f"{scenario_name}. "
            f"Available scenarios: "
            f"{available}"
        )

    scenario = scenarios[
        scenario_name
    ]

    overrides = (
        scenario.get(
            "overrides",
            {}
        )
    )

    config = deep_merge(
        config,
        overrides
    )

    config["scenario"] = {
        "name":
            scenario_name,

        "description":
            scenario.get(
                "description",
                ""
            ),

        "overrides":
            copy.deepcopy(
                overrides
            )
    }

    return config


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 60)
    print("SIMULATION SCENARIO CONFIG CHECK")
    print("=" * 60)

    for scenario_name in (
        get_available_scenarios()
    ):

        config = load_all_config(
            scenario_name=scenario_name
        )

        company = config[
            "company"
        ]

        print(
            f"\n{scenario_name}"
        )

        print(
            "Description:",
            config["scenario"][
                "description"
            ]
        )

        print(
            "October seasonality:",
            company.get(
                "seasonality_month_multipliers",
                {}
            ).get(
                "October"
            )
        )

        print(
            "Add-to-cart base:",
            company.get(
                "event_funnel_behavior",
                {}
            ).get(
                "base_add_to_cart_probability"
            )
        )

        print(
            "High promotion multiplier:",
            company.get(
                "promotion_behavior",
                {}
            )
            .get(
                "discount_band_multipliers",
                {}
            )
            .get(
                "high"
            )
        )

    print(
        "\nSIMULATION SCENARIO CONFIG CHECK PASSED."
    )