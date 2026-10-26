
from html import escape
from urllib.parse import urlencode

from src.runtime.run_workspace import RUN_ID_PATTERN
from src.services.run_history_service import VALID_STATUSES


# =====================================================
# PHASE 9.11.4A - RUN HISTORY HTML RENDERER
# =====================================================

STYLE = """
<style>
* { box-sizing: border-box; }

body {
    margin: 0;
    background: #f4f7fb;
    color: #17253d;
    font-family: Arial, sans-serif;
}

main {
    max-width: 1400px;
    margin: auto;
    padding: 36px 24px;
}

h1 { margin: 0 0 8px; }

.subtitle { color: #64748b; margin-bottom: 28px; }

.stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 24px;
}

.card, .panel {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 20px;
}

.card span {
    display: block;
    font-size: 13px;
    color: #64748b;
}

.card strong {
    display: block;
    margin-top: 8px;
    font-size: 28px;
}

.filters {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    align-items: end;
    margin-bottom: 22px;
}

.filters label {
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 12px;
    font-weight: bold;
}

select, button {
    padding: 10px;
    border: 1px solid #cbd5e1;
    border-radius: 7px;
    background: white;
}

button {
    background: #1d4ed8;
    color: white;
    cursor: pointer;
    border: none;
}

.table-wrap { overflow-x: auto; }

table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}

th, td {
    text-align: left;
    padding: 14px 12px;
    border-bottom: 1px solid #e2e8f0;
}

th {
    color: #64748b;
    background: #f8fafc;
}

code { font-size: 12px; }

.status {
    display: inline-block;
    padding: 5px 9px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: bold;
    background: #e2e8f0;
}

.completed { color: #166534; background: #dcfce7; }
.failed { color: #991b1b; background: #fee2e2; }
.timed_out { color: #991b1b; background: #fee2e2; }
.running { color: #1d4ed8; background: #dbeafe; }

.actions a {
    display: inline-block;
    margin: 3px 8px 3px 0;
    color: #1d4ed8;
    text-decoration: none;
}

.pagination {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 20px;
}

.pagination a {
    color: #1d4ed8;
    text-decoration: none;
    font-weight: bold;
}

.muted { color: #64748b; }

@media (max-width: 700px) {
    .stats { grid-template-columns: repeat(2, 1fr); }
    main { padding: 18px 12px; }
}
</style>
"""


def text(value):
    if value is None:
        return "—"

    return escape(str(value), quote=True)


def make_select(name, options, current):

    elements = []

    current = current if current is not None else ""

    for value, label in options:

        selected = (
            " selected"
            if value == current
            else ""
        )

        elements.append(
            f'<option value="{text(value)}"{selected}>'
            f'{text(label)}</option>'
        )

    return (
        f'<label>{text(name.replace("_", " ").title())}'
        f'<select name="{text(name)}">'
        + "".join(elements)
        + "</select></label>"
    )


# =====================================================
# SAFE RUN NAVIGATION
# =====================================================

def render_run_row(record):

    run_id = record["run_id"]
    status = record["status"]

    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError("Invalid run identifier")

    if status not in VALID_STATUSES:
        raise ValueError("Invalid run status")

    base = f"/api/v1/runs/{run_id}"

    actions = [
        ("Details", base),
    ]

    if status == "COMPLETED":

        actions.extend([
            ("Datasets", f"{base}/datasets"),
            ("Metrics", f"{base}/metrics"),
            ("Validations", f"{base}/validations"),
        ])

    links = " ".join(
        f'<a href="{text(url)}">{text(label)}</a>'
        for label, url in actions
    )

    duration = record.get("duration_seconds")

    duration_text = (
        "—"
        if duration is None
        else f"{duration:.3f}s"
    )

    return f"""
    <tr data-run-id="{text(run_id)}">
        <td><code>{text(run_id)}</code></td>
        <td>
            <span class="status {text(status.lower())}">
                {text(status)}
            </span>
        </td>
        <td>{text(record["scenario"])}</td>
        <td>
            {text(record["days"])} days /
            {text(record["customers"])} customers
        </td>
        <td>{text(record.get("started_at"))}</td>
        <td>{text(record.get("finished_at"))}</td>
        <td>{text(duration_text)}</td>
        <td class="actions">{links}</td>
    </tr>
    """


# =====================================================
# RENDER COMPLETE RUN HISTORY PAGE
# =====================================================

def render_run_history_html(history, scenarios):

    runs = history["runs"]

    filters = history["filters"]
    sorting = history["sort"]
    pagination = history["pagination"]

    status_options = [("", "All statuses")] + [
        (name, name)
        for name in sorted(VALID_STATUSES)
    ]

    scenario_options = [("", "All scenarios")] + [
        (name, name)
        for name in sorted(scenarios)
    ]

    sort_options = [
        ("started_at", "Start time"),
        ("created_at", "Creation time"),
        ("finished_at", "Finish time"),
        ("duration_seconds", "Duration"),
        ("run_id", "Run ID"),
    ]

    order_options = [
        ("desc", "Descending"),
        ("asc", "Ascending"),
    ]

    page_size_options = [
        ("5", "5"),
        ("10", "10"),
        ("20", "20"),
        ("50", "50"),
        ("100", "100"),
    ]

    controls = "".join([
        make_select(
            "status", status_options,
            filters["status"],
        ),
        make_select(
            "scenario", scenario_options,
            filters["scenario"],
        ),
        make_select(
            "sort_by", sort_options,
            sorting["by"],
        ),
        make_select(
            "order", order_options,
            sorting["order"],
        ),
        make_select(
            "page_size", page_size_options,
            str(pagination["page_size"]),
        ),
    ])

    rows = "".join(
        render_run_row(record)
        for record in runs
    )

    if not runs:
        rows = (
            '<tr><td colspan="8" class="muted">'
            "No matching simulation runs."
            "</td></tr>"
        )

    # ==========================================
    # PAGINATION LINKS
    # ==========================================

    query = {
        "sort_by": sorting["by"],
        "order": sorting["order"],
        "page_size": pagination["page_size"],
    }

    if filters["status"]:
        query["status"] = filters["status"]

    if filters["scenario"]:
        query["scenario"] = filters["scenario"]

    def page_url(page_number):

        parameters = {
            **query,
            "page": page_number,
        }

        return "/run-history?" + urlencode(parameters)

    previous = (
        f'<a href="{text(page_url(pagination["page"] - 1))}">'
        "Previous</a>"
        if pagination["has_previous"]
        else '<span class="muted">Previous</span>'
    )

    next_page = (
        f'<a href="{text(page_url(pagination["page"] + 1))}">'
        "Next</a>"
        if pagination["has_next"]
        else '<span class="muted">Next</span>'
    )

    counts = history["status_counts"]

    failed_count = (
        counts.get("FAILED", 0)
        + counts.get("TIMED_OUT", 0)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport"
          content="width=device-width, initial-scale=1">
    <title>M14 Simulation Run History</title>
    {STYLE}
</head>
<body>
<main>
    <h1>M14 — Simulation Run History</h1>
    <p class="subtitle">
        Read-only history of D2C simulation executions.
    </p>

    <section class="stats">
        <div class="card">
            <span>Total Runs</span>
            <strong>{history["total_runs"]}</strong>
        </div>
        <div class="card">
            <span>Matching Runs</span>
            <strong>{history["filtered_total"]}</strong>
        </div>
        <div class="card">
            <span>Completed</span>
            <strong>{counts.get("COMPLETED", 0)}</strong>
        </div>
        <div class="card">
            <span>Failed / Timed Out</span>
            <strong>{failed_count}</strong>
        </div>
    </section>

    <section class="panel">
        <form class="filters"
              method="get"
              action="/run-history">
            {controls}
            <button type="submit">Apply Filters</button>
        </form>

        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>Run ID</th>
                        <th>Status</th>
                        <th>Scenario</th>
                        <th>Configuration</th>
                        <th>Started</th>
                        <th>Finished</th>
                        <th>Duration</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>

        <nav class="pagination">
            {previous}
            <span>
                Page {pagination["page"]}
                of {pagination["total_pages"] or 1}
            </span>
            {next_page}
        </nav>
    </section>
</main>
</body>
</html>
"""