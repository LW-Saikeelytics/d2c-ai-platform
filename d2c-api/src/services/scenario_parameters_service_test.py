
from src.config.scenario_registry import (
    SCENARIO_FILE,
    load_scenario_registry,
)

from src.services.scenario_parameters_service import (
    ScenarioNotFoundError,
    get_scenario_parameters,
)


# =====================================================
# PHASE 9.10.2 - SCENARIO PARAMETERS TEST
# =====================================================

def test_scenario_parameters():

    print("=" * 70)
    print("PHASE 9 - SCENARIO PARAMETERS SERVICE")
    print("=" * 70)

    original_bytes = SCENARIO_FILE.read_bytes()

    registry = load_scenario_registry()

    expected_counts = {
        "baseline": 0,
        "festive_peak": 8,
        "promotion_heavy": 4,
        "low_inventory": 10,
        "slow_demand": 14,
    }

    assert set(registry["scenarios"]) == set(
        expected_counts
    )

    print("Five registered scenarios discovered: PASS")

    # ==========================================
    # TEST 1 - ALL SCENARIOS
    # ==========================================

    for name, expected_count in expected_counts.items():

        details = get_scenario_parameters(name)

        assert details["name"] == name

        assert details["description"] == (
            registry["scenarios"][name]["description"]
        )

        assert details["overrides"] == (
            registry["scenarios"][name]["overrides"]
        )

        assert details["parameter_count"] == (
            expected_count
        )

        print(
            f"{name}: {expected_count} "
            "override parameters (PASS)"
        )

    # ==========================================
    # TEST 2 - BASELINE CONFIGURATION
    # ==========================================

    baseline = get_scenario_parameters(
        "baseline"
    )

    assert baseline["is_default"] is True
    assert baseline["overrides"] == {}
    assert baseline["override_sections"] == []

    print("Baseline default configuration: PASS")

    # ==========================================
    # TEST 3 - FESTIVE PEAK PARAMETERS
    # ==========================================

    festive = get_scenario_parameters(
        "festive_peak"
    )

    company = festive["overrides"]["company"]

    assert company[
        "seasonality_month_multipliers"
    ]["October"] == 1.45

    assert company[
        "event_funnel_behavior"
    ]["base_add_to_cart_probability"] == 0.42

    assert festive["override_sections"] == [
        "company"
    ]

    print("Festive peak parameters verified: PASS")

    # ==========================================
    # TEST 4 - PROMOTION PARAMETERS
    # ==========================================

    promotion = get_scenario_parameters(
        "promotion_heavy"
    )

    assert promotion["overrides"]["company"][
        "promotion_behavior"
    ]["discount_band_multipliers"]["high"] == 1.55

    print("Promotion parameters verified: PASS")

    # ==========================================
    # TEST 5 - INVENTORY PARAMETERS
    # ==========================================

    inventory = get_scenario_parameters(
        "low_inventory"
    )

    regions = inventory["overrides"]["company"][
        "inventory_behavior"
    ]["regional_overrides"]

    assert len(regions) == 5

    assert regions["North"]["PRD-BED-004"] == (
        "out_of_stock"
    )

    print("Regional inventory parameters: PASS")

    # ==========================================
    # TEST 6 - SLOW DEMAND PARAMETERS
    # ==========================================

    slow = get_scenario_parameters(
        "slow_demand"
    )

    assert slow["overrides"]["company"][
        "weekday_activity_multipliers"
    ]["Monday"] == 0.75

    assert slow["overrides"]["company"][
        "event_funnel_behavior"
    ]["base_add_to_cart_probability"] == 0.28

    print("Slow demand parameters verified: PASS")

    # ==========================================
    # TEST 7 - UNKNOWN SCENARIO
    # ==========================================

    try:

        get_scenario_parameters(
            "unknown_scenario"
        )

    except ScenarioNotFoundError:
        print("Unknown scenario rejected: PASS")

    else:
        raise AssertionError(
            "Unknown scenario was accepted"
        )

    # ==========================================
    # TEST 8 - UNSAFE IDENTIFIER
    # ==========================================

    try:

        get_scenario_parameters(
            "../baseline"
        )

    except ValueError:
        print("Unsafe scenario identifier rejected: PASS")

    else:
        raise AssertionError(
            "Unsafe scenario identifier accepted"
        )

    # ==========================================
    # TEST 9 - INVALID INPUT TYPE
    # ==========================================

    try:

        get_scenario_parameters(123)

    except ValueError:
        print("Invalid scenario input type rejected: PASS")

    else:
        raise AssertionError(
            "Invalid scenario input accepted"
        )

    # ==========================================
    # TEST 10 - RETURNED DATA IS INDEPENDENT
    # ==========================================

    modified = get_scenario_parameters(
        "festive_peak"
    )

    modified["overrides"]["company"][
        "event_funnel_behavior"
    ]["base_add_to_cart_probability"] = 0

    fresh = get_scenario_parameters(
        "festive_peak"
    )

    assert fresh["overrides"]["company"][
        "event_funnel_behavior"
    ]["base_add_to_cart_probability"] == 0.42

    print("Returned configuration isolation: PASS")

    # ==========================================
    # TEST 11 - SOURCE REGISTRY UNCHANGED
    # ==========================================

    assert SCENARIO_FILE.read_bytes() == (
        original_bytes
    )

    print("Phase 6 scenario registry unchanged: PASS")

    # ==========================================
    # FINAL SUMMARY
    # ==========================================

    print()
    print("=== SCENARIO PARAMETER SUMMARY ===")

    for name, count in expected_counts.items():
        print(f"{name}: {count}")

    print()
    print(
        "Total configured override values:",
        sum(expected_counts.values())
    )

    print()
    print("Phase 6 files modified: NO")
    print("Generator execution performed: NO")
    print("Scenario HTTP detail endpoint enabled: NO")

    print()
    print("SCENARIO PARAMETERS SERVICE TEST PASSED.")


if __name__ == "__main__":
    test_scenario_parameters()
