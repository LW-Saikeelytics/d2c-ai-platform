
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app

from src.config.scenario_registry import (
    SCENARIO_FILE,
    load_scenario_registry,
)


# =====================================================
# PHASE 9.10.3 - SCENARIO PARAMETERS API TEST
# =====================================================

BASE_URL = "/api/v1/scenarios"


def test_scenario_parameters_endpoint():

    print("=" * 70)
    print("PHASE 9 - SCENARIO PARAMETERS API")
    print("=" * 70)

    client = TestClient(app)

    original_registry = SCENARIO_FILE.read_bytes()

    registry = load_scenario_registry()

    expected_counts = {
        "baseline": 0,
        "festive_peak": 8,
        "promotion_heavy": 4,
        "low_inventory": 10,
        "slow_demand": 14,
    }

    # ==========================================
    # TEST 1 - ALL FIVE SCENARIOS
    # ==========================================

    for name, count in expected_counts.items():

        response = client.get(
            f"{BASE_URL}/{name}"
        )

        assert response.status_code == 200, (
            response.text
        )

        details = response.json()

        assert details["name"] == name
        assert details["parameter_count"] == count

        assert details["description"] == (
            registry["scenarios"][name]["description"]
        )

        assert details["overrides"] == (
            registry["scenarios"][name]["overrides"]
        )

        assert details["is_default"] == (
            name == "baseline"
        )

        print(f"{name} -> HTTP 200 (PASS)")

    # ==========================================
    # TEST 2 - BASELINE SCENARIO
    # ==========================================

    baseline = client.get(
        f"{BASE_URL}/baseline"
    ).json()

    assert baseline["is_default"] is True
    assert baseline["overrides"] == {}
    assert baseline["parameter_count"] == 0

    print("Baseline default scenario: PASS")

    # ==========================================
    # TEST 3 - FESTIVE PEAK PARAMETERS
    # ==========================================

    festive = client.get(
        f"{BASE_URL}/festive_peak"
    ).json()

    company = festive["overrides"]["company"]

    assert company[
        "seasonality_month_multipliers"
    ]["October"] == 1.45

    assert company[
        "event_funnel_behavior"
    ]["base_add_to_cart_probability"] == 0.42

    assert festive["parameter_count"] == 8

    print("Festive peak parameters: PASS")

    # ==========================================
    # TEST 4 - REGIONAL INVENTORY
    # ==========================================

    inventory = client.get(
        f"{BASE_URL}/low_inventory"
    ).json()

    regions = inventory["overrides"]["company"][
        "inventory_behavior"
    ]["regional_overrides"]

    assert len(regions) == 5
    assert regions["North"]["PRD-BED-004"] == (
        "out_of_stock"
    )

    print("Regional inventory parameters: PASS")

    # ==========================================
    # TEST 5 - ORIGINAL LIST ENDPOINT
    # ==========================================

    listing = client.get(BASE_URL)

    assert listing.status_code == 200

    print("Existing scenario listing preserved: PASS")

    # ==========================================
    # TEST 6 - UNKNOWN SCENARIO
    # ==========================================

    unknown = client.get(
        f"{BASE_URL}/unknown_scenario"
    )

    assert unknown.status_code == 404

    print("Unknown scenario -> HTTP 404: PASS")

    # ==========================================
    # TEST 7 - INVALID IDENTIFIER
    # ==========================================

    invalid = client.get(
        f"{BASE_URL}/invalid.scenario"
    )

    assert invalid.status_code == 422

    print("Invalid scenario ID -> HTTP 422: PASS")

    # ==========================================
    # TEST 8 - REGISTRY FAILURE
    # ==========================================

    with patch(
        "src.api.main.get_scenario_parameters",
        side_effect=FileNotFoundError(
            "PRIVATE_REGISTRY_PATH"
        ),
    ):

        failed = client.get(
            f"{BASE_URL}/festive_peak"
        )

        assert failed.status_code == 503

        assert "PRIVATE_REGISTRY_PATH" not in (
            failed.text
        )

    print("Registry unavailable -> HTTP 503: PASS")
    print("Private error details hidden: PASS")

    # ==========================================
    # TEST 9 - RESPONSE PRIVACY
    # ==========================================

    assert "C:\\" not in str(festive)
    assert "file_path" not in str(festive)

    print("Internal filesystem paths hidden: PASS")

    # ==========================================
    # TEST 10 - OPENAPI REGISTRATION
    # ==========================================

    schema_response = client.get(
        "/openapi.json"
    )

    assert schema_response.status_code == 200

    path = (
        "/api/v1/scenarios/{scenario_name}"
    )

    assert "get" in schema_response.json()[
        "paths"
    ][path]

    print("Scenario endpoint registered in OpenAPI: PASS")

    # ==========================================
    # TEST 11 - ORIGINAL REGISTRY UNCHANGED
    # ==========================================

    assert SCENARIO_FILE.read_bytes() == (
        original_registry
    )

    print("Phase 6 scenario registry unchanged: PASS")

    # ==========================================
    # FINAL SUMMARY
    # ==========================================

    print()
    print("=== SCENARIO API SUMMARY ===")

    for name, count in expected_counts.items():
        print(f"{name}: {count} overrides")

    print()
    print(
        "Total configured overrides:",
        sum(expected_counts.values())
    )

    print()
    print("Generator execution performed: NO")
    print("Phase 6 files modified: NO")
    print("Scenario configuration changes: NO")

    print()
    print("SCENARIO PARAMETERS API TEST PASSED.")


if __name__ == "__main__":
    test_scenario_parameters_endpoint()
