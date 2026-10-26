
from copy import deepcopy

from src.services.run_history_service import (
    list_run_history,
)

from src.services.enhanced_run_history_service import (
    build_history_overview,
    get_enhanced_run_history,
)


KNOWN_RUN = (
    "api_run_ebaaf56bd9b14c1d9fca1af532387316"
)

LEGACY_RUN = (
    "api_run_71e00acdec7c445fbee437ed68795f29"
)


def test_enhanced_run_history():

    print("=" * 70)
    print("PHASE 9 - ENHANCED RUN-HISTORY SERVICE")
    print("=" * 70)

    original = list_run_history()
    original_copy = deepcopy(original)

    overview = get_enhanced_run_history()

    # ==========================================
    # TEST 1 - EXISTING HISTORY
    # ==========================================

    assert overview["total"] == len(original)
    assert overview["total"] >= 4

    print("Existing run history retrieved: PASS")

    assert len(overview["runs"]) == overview["total"]

    print("History record count verified: PASS")

    # ==========================================
    # TEST 2 - STATUS SUMMARY
    # ==========================================

    counts = overview["status_counts"]

    assert set(counts) == {
        "RESERVED",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        "TIMED_OUT",
    }

    assert sum(counts.values()) == overview["total"]

    print("Five lifecycle statuses summarized: PASS")

    # ==========================================
    # TEST 3 - SCENARIO SUMMARY
    # ==========================================

    scenario_counts = overview["scenario_counts"]

    assert sum(scenario_counts.values()) == (
        overview["total"]
    )

    assert scenario_counts.get("baseline", 0) >= 4

    print("Simulation scenarios summarized: PASS")

    # ==========================================
    # TEST 4 - EXECUTION DURATION
    # ==========================================

    known = next(
        item
        for item in overview["runs"]
        if item["run_id"] == KNOWN_RUN
    )

    assert known["status"] == "COMPLETED"

    assert (
        isinstance(known["duration_seconds"], float)
        and known["duration_seconds"] >= 0
    )

    print("Execution duration calculated: PASS")

    # ==========================================
    # TEST 5 - HISTORICAL COMPATIBILITY
    # ==========================================

    legacy = next(
        item
        for item in overview["runs"]
        if item["run_id"] == LEGACY_RUN
    )

    assert legacy["created_at"] is None
    assert legacy["duration_seconds"] is not None

    print("Legacy missing creation timestamp: PASS")

    # ==========================================
    # TEST 6 - NAVIGATION LINKS
    # ==========================================

    links = known["links"]

    base = f"/api/v1/runs/{KNOWN_RUN}"

    assert links == {
        "details": base,
        "datasets": f"{base}/datasets",
        "metrics": f"{base}/metrics",
        "validations": f"{base}/validations",
    }

    print("Completed run navigation links: PASS")

    # ==========================================
    # TEST 7 - CONTROLLED LIFECYCLE FIXTURES
    # ==========================================

    fixtures = [
        {
            "run_id": "api_run_" + ("a" * 32),
            "status": "RESERVED",
            "scenario": "baseline",
            "days": 7,
            "customers": 100,
            "created_at": "2026-10-26T10:00:00+00:00",
            "started_at": None,
            "finished_at": None,
            "exit_code": None,
        },
        {
            "run_id": "api_run_" + ("b" * 32),
            "status": "RUNNING",
            "scenario": "festive_peak",
            "days": 7,
            "customers": 100,
            "created_at": "2026-10-26T10:01:00+00:00",
            "started_at": "2026-10-26T10:01:01+00:00",
            "finished_at": None,
            "exit_code": None,
        },
        {
            "run_id": "api_run_" + ("c" * 32),
            "status": "FAILED",
            "scenario": "baseline",
            "days": 7,
            "customers": 100,
            "created_at": "2026-10-26T10:02:00+00:00",
            "started_at": None,
            "finished_at": "2026-10-26T10:02:02+00:00",
            "exit_code": None,
        },
        {
            "run_id": "api_run_" + ("d" * 32),
            "status": "TIMED_OUT",
            "scenario": "slow_demand",
            "days": 7,
            "customers": 100,
            "created_at": "2026-10-26T10:03:00+00:00",
            "started_at": "2026-10-26T10:03:01+00:00",
            "finished_at": "2026-10-26T10:03:11+00:00",
            "exit_code": None,
        },
    ]

    fixture_copy = deepcopy(fixtures)

    fixture_overview = build_history_overview(
        fixtures
    )

    assert fixture_overview["total"] == 4

    for status in (
        "RESERVED",
        "RUNNING",
        "FAILED",
        "TIMED_OUT",
    ):
        assert fixture_overview[
            "status_counts"
        ][status] == 1

    print("Reserved, running and failed states: PASS")

    assert all(
        item["duration_seconds"] is None
        for item in fixture_overview["runs"][:3]
    )

    assert fixture_overview["runs"][3][
        "duration_seconds"
    ] == 10.0

    print("Missing and available durations: PASS")

    for item in fixture_overview["runs"]:

        assert set(item["links"]) == {"details"}

    print("Incomplete-run navigation restricted: PASS")

    # ==========================================
    # TEST 8 - INVALID HISTORY
    # ==========================================

    invalid = deepcopy(fixtures)

    invalid[0]["run_id"] = "../unsafe"

    try:
        build_history_overview(invalid)
    except ValueError:
        print("Unsafe run identifier rejected: PASS")
    else:
        raise AssertionError("Unsafe run ID accepted")

    duplicate = deepcopy(fixtures)
    duplicate[1]["run_id"] = duplicate[0]["run_id"]

    try:
        build_history_overview(duplicate)
    except ValueError:
        print("Duplicate run identifier rejected: PASS")
    else:
        raise AssertionError("Duplicate run ID accepted")

    # ==========================================
    # TEST 9 - NO MUTATIONS
    # ==========================================

    assert original == original_copy
    assert fixtures == fixture_copy

    print("Original records unchanged: PASS")

    assert "generated_run_directory" not in (
        str(overview)
    )

    print("Private dataset paths hidden: PASS")

    # ==========================================
    # FINAL SUMMARY
    # ==========================================

    print()
    print("=== ENHANCED RUN HISTORY ===")
    print("Total runs:", overview["total"])
    print("Status counts:", overview["status_counts"])
    print("Scenario counts:", overview["scenario_counts"])

    print()
    print("Generator execution performed: NO")
    print("Existing run records modified: NO")
    print("Existing history API modified: NO")

    print()
    print("ENHANCED RUN-HISTORY SERVICE TEST PASSED.")


if __name__ == "__main__":
    test_enhanced_run_history()
