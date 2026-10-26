
from src.config.environment_settings import (
    load_environment_settings,
)


def test_environment_settings():

    valid_cases = [
        ("default", {}, "development", False),
        (
            "development_disabled",
            {"M14_ENV": "development"},
            "development",
            False,
        ),
        (
            "development_enabled",
            {
                "M14_ENV": "development",
                "M14_ENABLE_SIMULATION_START": "1",
            },
            "development",
            True,
        ),
        (
            "testing_disabled",
            {"M14_ENV": "testing"},
            "testing",
            False,
        ),
        (
            "production_disabled",
            {"M14_ENV": "production"},
            "production",
            False,
        ),
    ]

    for name, values, expected_env, expected_enabled in valid_cases:

        config = load_environment_settings(values)

        assert config.environment == expected_env
        assert config.simulation_start_enabled is expected_enabled

        print(f"{name}: PASS")

    invalid_cases = {
        "invalid_environment": {
            "M14_ENV": "unknown",
        },
        "invalid_execution_flag": {
            "M14_ENABLE_SIMULATION_START": "yes",
        },
        "production_execution_blocked": {
            "M14_ENV": "production",
            "M14_ENABLE_SIMULATION_START": "1",
        },
    }

    for name, values in invalid_cases.items():

        try:
            load_environment_settings(values)

        except ValueError:
            print(f"{name}: REJECTED (PASS)")

        else:
            raise AssertionError(
                f"Invalid configuration accepted: {name}"
            )

    print()
    print("ENVIRONMENT SETTINGS TEST PASSED.")


if __name__ == "__main__":
    test_environment_settings()
