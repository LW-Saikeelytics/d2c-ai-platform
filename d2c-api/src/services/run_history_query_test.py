
from src.services.enhanced_run_history_service import (
    get_enhanced_run_history,
)

from src.services.run_history_query_service import (
    get_run_history_page,
    query_run_history,
)


KNOWN_RUN = (
    "api_run_ebaaf56bd9b14c1d9fca1af532387316"
)

LEGACY_RUN = (
    "api_run_71e00acdec7c445fbee437ed68795f29"
)


def test_history_queries():

    print("=" * 70)
    print("PHASE 9 - RUN HISTORY FILTERING AND PAGINATION")
    print("=" * 70)

    # ==========================================
    # TEST 1 - ORIGINAL HISTORY
    # ==========================================

    overview = get_enhanced_run_history()

    result = get_run_history_page()

    assert result["total_runs"] == overview["total"]
    assert result["total_runs"] >= 4

    print("Existing run history retrieved: PASS")

    # ==========================================
    # TEST 2 - DEFAULT SORTING
    # ==========================================

    assert result["runs"][0]["run_id"] == KNOWN_RUN

    print("Newest-first sorting: PASS")

    # ==========================================
    # TEST 3 - STATUS FILTER
    # ==========================================

    completed = get_run_history_page(
        status="COMPLETED"
    )

    assert all(
        run["status"] == "COMPLETED"
        for run in completed["runs"]
    )

    assert completed["filtered_total"] >= 4

    print("Completed-status filter: PASS")

    # ==========================================
    # TEST 4 - SCENARIO FILTER
    # ==========================================

    baseline = get_run_history_page(
        scenario="baseline"
    )

    assert baseline["filtered_total"] >= 4

    assert all(
        run["scenario"] == "baseline"
        for run in baseline["runs"]
    )

    print("Scenario filter: PASS")

    # ==========================================
    # TEST 5 - COMBINED FILTERS
    # ==========================================

    combined = get_run_history_page(
        status="COMPLETED",
        scenario="baseline",
    )

    assert combined["filtered_total"] >= 4

    print("Combined filters: PASS")

    # ==========================================
    # TEST 6 - FILTER WITH NO MATCHES
    # ==========================================

    empty = get_run_history_page(
        scenario="festive_peak",
    )

    assert empty["filtered_total"] == 0
    assert empty["runs"] == []
    assert empty["pagination"]["total_pages"] == 0

    print("Empty filter results: PASS")

    # ==========================================
    # TEST 7 - PAGINATION
    # ==========================================

    first = get_run_history_page(
        page=1,
        page_size=2,
    )

    second = get_run_history_page(
        page=2,
        page_size=2,
    )

    assert len(first["runs"]) == 2
    assert len(second["runs"]) == 2

    assert first["pagination"]["has_next"]
    assert second["pagination"]["has_previous"]

    first_ids = {
        item["run_id"]
        for item in first["runs"]
    }

    second_ids = {
        item["run_id"]
        for item in second["runs"]
    }

    assert first_ids.isdisjoint(second_ids)

    print("Multi-page history retrieval: PASS")

    # ==========================================
    # TEST 8 - OUT-OF-RANGE PAGE
    # ==========================================

    beyond = get_run_history_page(
        page=999,
        page_size=2,
    )

    assert beyond["runs"] == []

    print("Out-of-range page handled: PASS")

    # ==========================================
    # TEST 9 - ASCENDING SORT
    # ==========================================

    ascending = get_run_history_page(
        sort_by="started_at",
        order="asc",
    )

    assert ascending["runs"][0]["run_id"] == (
        LEGACY_RUN
    )

    print("Oldest-first sorting: PASS")

    # ==========================================
    # TEST 10 - LEGACY TIMESTAMPS
    # ==========================================

    created = get_run_history_page(
        sort_by="created_at",
        order="desc",
    )

    assert created["runs"][-1]["run_id"] == (
        LEGACY_RUN
    )

    assert created["runs"][-1]["created_at"] is None

    print("Missing historical timestamps handled: PASS")

    # ==========================================
    # TEST 11 - DURATION SORT
    # ==========================================

    durations = get_run_history_page(
        sort_by="duration_seconds",
        order="desc",
    )

    values = [
        run["duration_seconds"]
        for run in durations["runs"]
        if run["duration_seconds"] is not None
    ]

    assert values == sorted(
        values,
        reverse=True,
    )

    print("Execution-duration sorting: PASS")

    # ==========================================
    # TEST 12 - INVALID QUERY PARAMETERS
    # ==========================================

    invalid_queries = [
        {"status": "INVALID"},
        {"scenario": "not_registered"},
        {"sort_by": "unknown_field"},
        {"order": "sideways"},
        {"page": 0},
        {"page": True},
        {"page_size": 0},
        {"page_size": 101},
    ]

    for invalid in invalid_queries:

        try:
            query_run_history(
                overview,
                **invalid,
            )

        except ValueError:
            pass

        else:
            raise AssertionError(
                f"Invalid query accepted: {invalid}"
            )

    print("Invalid query parameters rejected: PASS")

    # ==========================================
    # TEST 13 - PUBLIC RESPONSE PROTECTION
    # ==========================================

    assert "generated_run_directory" not in (
        str(result)
    )

    assert "C:\\" not in str(result)

    print("Internal filesystem paths hidden: PASS")

    print()
    print("=== HISTORY QUERY SUMMARY ===")
    print("Total runs:", result["total_runs"])
    print("Page size:", result["pagination"]["page_size"])
    print("Status counts:", result["status_counts"])
    print("Scenario counts:", result["scenario_counts"])

    print()
    print("Generator execution performed: NO")
    print("Existing run records modified: NO")
    print("History HTTP endpoints modified: NO")

    print()
    print("RUN HISTORY QUERY SERVICE TEST PASSED.")


if __name__ == "__main__":
    test_history_queries()
