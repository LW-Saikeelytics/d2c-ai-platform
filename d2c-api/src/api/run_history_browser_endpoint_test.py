
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app
from src.runtime.run_workspace import RUNTIME_ROOT


# =====================================================
# PHASE 9.11.4B - BROWSER HISTORY ENDPOINT TEST
# =====================================================

ENDPOINT = "/run-history"

KNOWN_RUN = (
    "api_run_ebaaf56bd9b14c1d9fca1af532387316"
)

LEGACY_RUN = (
    "api_run_71e00acdec7c445fbee437ed68795f29"
)


def test_browser_history_endpoint():

    print("=" * 70)
    print("PHASE 9 - BROWSER RUN-HISTORY ENDPOINT")
    print("=" * 70)

    client = TestClient(app)

    status_file = (
        RUNTIME_ROOT
        / KNOWN_RUN
        / "execution_status.json"
    )

    original_status_bytes = status_file.read_bytes()

    # ==========================================
    # TEST 1 - BROWSER PAGE RESPONSE
    # ==========================================

    response = client.get(ENDPOINT)

    assert response.status_code == 200, response.text

    assert "text/html" in response.headers[
        "content-type"
    ]

    print("Browser history -> HTTP 200: PASS")
    print("HTML content type returned: PASS")

    # ==========================================
    # TEST 2 - REAL HISTORY DISPLAY
    # ==========================================

    html = response.text

    assert "M14" in html
    assert "Simulation Run History" in html

    assert html.count('data-run-id="') == 4

    assert KNOWN_RUN in html
    assert LEGACY_RUN in html

    print("Four historical runs displayed: PASS")

    # ==========================================
    # TEST 3 - FILTER CONTROLS
    # ==========================================

    for name in (
        "status",
        "scenario",
        "sort_by",
        "order",
        "page_size",
    ):
        assert f'name="{name}"' in html

    assert "Apply Filters" in html

    print("Interactive filter controls: PASS")

    # ==========================================
    # TEST 4 - SCENARIO FILTER
    # ==========================================

    filtered = client.get(
        ENDPOINT,
        params={"scenario": "baseline"},
    )

    assert filtered.status_code == 200

    assert filtered.text.count(
        'data-run-id="'
    ) == 4

    print("Scenario filtering: PASS")

    # ==========================================
    # TEST 5 - STATUS FILTER
    # ==========================================

    completed = client.get(
        ENDPOINT,
        params={"status": "COMPLETED"},
    )

    assert completed.status_code == 200

    assert completed.text.count(
        'data-run-id="'
    ) == 4

    print("Execution-status filtering: PASS")

    # ==========================================
    # TEST 6 - EMPTY FILTER RESULT
    # ==========================================

    empty = client.get(
        ENDPOINT,
        params={"scenario": "festive_peak"},
    )

    assert empty.status_code == 200

    assert "No matching simulation runs." in (
        empty.text
    )

    print("Empty history message: PASS")

    # ==========================================
    # TEST 7 - PAGINATION
    # ==========================================

    first = client.get(
        ENDPOINT,
        params={
            "page": 1,
            "page_size": 2,
        },
    )

    second = client.get(
        ENDPOINT,
        params={
            "page": 2,
            "page_size": 2,
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200

    assert first.text.count(
        'data-run-id="'
    ) == 2

    assert second.text.count(
        'data-run-id="'
    ) == 2

    assert "page=2" in first.text
    assert "page=1" in second.text

    print("Browser pagination: PASS")

    # ==========================================
    # TEST 8 - SORTING
    # ==========================================

    ascending = client.get(
        ENDPOINT,
        params={
            "sort_by": "started_at",
            "order": "asc",
        },
    )

    assert ascending.status_code == 200

    assert ascending.text.find(LEGACY_RUN) < (
        ascending.text.find(KNOWN_RUN)
    )

    print("Oldest-first sorting: PASS")

    # ==========================================
    # TEST 9 - RUN NAVIGATION
    # ==========================================

    base = f"/api/v1/runs/{KNOWN_RUN}"

    for suffix in (
        "",
        "/datasets",
        "/metrics",
        "/validations",
    ):
        assert f"{base}{suffix}" in html

    print("Run detail navigation links: PASS")

    # ==========================================
    # TEST 10 - INVALID QUERIES
    # ==========================================

    invalid_cases = [
        {"status": "UNKNOWN"},
        {"scenario": "unknown_scenario"},
        {"sort_by": "private_field"},
        {"order": "invalid"},
        {"page": 0},
        {"page_size": 101},
    ]

    for params in invalid_cases:

        invalid = client.get(
            ENDPOINT,
            params=params,
        )

        assert invalid.status_code == 422, (
            params,
            invalid.text,
        )

    print("Invalid query -> HTTP 422: PASS")

    # ==========================================
    # TEST 11 - HISTORY SERVICE FAILURE
    # ==========================================

    with patch(
        "src.api.main.get_run_history_page",
        side_effect=RuntimeError(
            "PRIVATE_HISTORY_ERROR"
        ),
    ):

        failed = client.get(ENDPOINT)

        assert failed.status_code == 500

        assert "PRIVATE_HISTORY_ERROR" not in (
            failed.text
        )

    print("History failure -> HTTP 500: PASS")

    # ==========================================
    # TEST 12 - HTML RENDERER FAILURE
    # ==========================================

    with patch(
        "src.api.main.render_run_history_html",
        side_effect=ValueError(
            "PRIVATE_RENDER_ERROR"
        ),
    ):

        failed = client.get(ENDPOINT)

        assert failed.status_code == 500

        assert "PRIVATE_RENDER_ERROR" not in (
            failed.text
        )

    print("Renderer failure -> HTTP 500: PASS")
    print("Private error details hidden: PASS")

    # ==========================================
    # TEST 13 - BROWSER SECURITY HEADERS
    # ==========================================

    assert response.headers[
        "cache-control"
    ] == "no-store"

    assert response.headers[
        "x-content-type-options"
    ] == "nosniff"

    assert (
        "Content-Security-Policy"
        in response.headers
    )

    print("Browser security headers: PASS")

    # ==========================================
    # TEST 14 - EXISTING APIS
    # ==========================================

    original = client.get("/api/v1/runs")

    queried = client.get("/api/v1/run-history")

    assert original.status_code == 200
    assert queried.status_code == 200

    assert original.json()["total"] == 4
    assert queried.json()["total_runs"] == 4

    print("Existing history APIs preserved: PASS")

    # ==========================================
    # TEST 15 - FILE INTEGRITY
    # ==========================================

    assert status_file.read_bytes() == (
        original_status_bytes
    )

    assert "generated_run_directory" not in html
    assert "C:\\" not in html

    print("Existing run record unchanged: PASS")
    print("Private filesystem paths hidden: PASS")

    # ==========================================
    # FINAL SUMMARY
    # ==========================================

    print()
    print("=== BROWSER HISTORY SUMMARY ===")
    print("HTTP status: 200")
    print("Displayed runs: 4")
    print("Browser path: /run-history")
    print("History query API: /api/v1/run-history")

    print()
    print("Generator execution performed: NO")
    print("Existing run records modified: NO")

    print()
    print(
        "BROWSER RUN-HISTORY ENDPOINT TEST PASSED."
    )


if __name__ == "__main__":
    test_browser_history_endpoint()
