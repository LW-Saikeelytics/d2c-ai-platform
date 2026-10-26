
from copy import deepcopy

from src.config.scenario_registry import (
    get_supported_scenarios,
)

from src.services.run_history_query_service import (
    get_run_history_page,
)

from src.api.run_history_view import (
    render_run_history_html,
)


KNOWN_RUN = (
    "api_run_ebaaf56bd9b14c1d9fca1af532387316"
)


def test_run_history_view():

    print("=" * 70)
    print("PHASE 9 - RUN HISTORY HTML VIEW")
    print("=" * 70)

    scenarios = get_supported_scenarios()

    history = get_run_history_page()

    html = render_run_history_html(
        history,
        scenarios,
    )

    assert "<!DOCTYPE html>" in html

    print("Valid HTML document generated: PASS")

    assert "M14 — Simulation Run History" in html

    print("Page title rendered: PASS")

    assert html.count('data-run-id="') == 4

    print("Four historical runs displayed: PASS")

    assert KNOWN_RUN in html

    print("Existing simulation IDs displayed: PASS")

    assert "Apply Filters" in html

    for name in (
        "status",
        "scenario",
        "sort_by",
        "order",
        "page_size",
    ):
        assert f'name="{name}"' in html

    print("Filtering and sorting controls: PASS")

    for scenario in scenarios:
        assert f'value="{scenario}"' in html

    print("All five scenarios selectable: PASS")

    for suffix in (
        "",
        "/datasets",
        "/metrics",
        "/validations",
    ):
        assert (
            f"/api/v1/runs/{KNOWN_RUN}{suffix}"
            in html
        )

    print("Run navigation links rendered: PASS")

    # ==========================================
    # TEST PAGINATION
    # ==========================================

    first = get_run_history_page(
        page=1,
        page_size=2,
    )

    paginated_html = render_run_history_html(
        first,
        scenarios,
    )

    assert paginated_html.count(
        'data-run-id="'
    ) == 2

    assert "page=2" in paginated_html

    print("Pagination navigation rendered: PASS")

    # ==========================================
    # TEST EMPTY HISTORY RESULT
    # ==========================================

    empty = get_run_history_page(
        scenario="festive_peak",
    )

    empty_html = render_run_history_html(
        empty,
        scenarios,
    )

    assert "No matching simulation runs." in (
        empty_html
    )

    print("Empty history message displayed: PASS")

    # ==========================================
    # TEST HTML ESCAPING
    # ==========================================

    unsafe = deepcopy(history)

    unsafe["runs"][0]["scenario"] = (
        "<script>alert(1)</script>"
    )

    escaped_html = render_run_history_html(
        unsafe,
        scenarios,
    )

    assert "<script>alert(1)</script>" not in (
        escaped_html
    )

    assert "&lt;script&gt;" in escaped_html

    print("Unsafe HTML content escaped: PASS")

    # ==========================================
    # TEST INVALID RUN IDENTIFIER
    # ==========================================

    invalid = deepcopy(history)

    invalid["runs"][0]["run_id"] = "../unsafe"

    try:
        render_run_history_html(
            invalid,
            scenarios,
        )

    except ValueError:
        print("Unsafe run identifier rejected: PASS")

    else:
        raise AssertionError(
            "Unsafe run identifier accepted"
        )

    # ==========================================
    # TEST PRIVATE DATA PROTECTION
    # ==========================================

    assert "generated_run_directory" not in html
    assert "C:\\" not in html

    print("Private filesystem paths hidden: PASS")

    print()
    print("=== HISTORY VIEW SUMMARY ===")
    print("Runs displayed:", history["total_runs"])
    print("Supported scenarios:", len(scenarios))
    print("Filter controls: 5")

    print()
    print("Browser endpoint enabled: NO")
    print("Generator execution performed: NO")
    print("Existing run records modified: NO")

    print()
    print("RUN HISTORY HTML VIEW TEST PASSED.")


if __name__ == "__main__":
    test_run_history_view()
