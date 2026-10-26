
import math

from datetime import datetime, timezone

from src.config.scenario_registry import (
    get_supported_scenarios,
)

from src.services.run_history_service import (
    VALID_STATUSES,
)

from src.services.enhanced_run_history_service import (
    get_enhanced_run_history,
)


# =====================================================
# PHASE 9.11.3A - RUN HISTORY QUERY SERVICE
# =====================================================

SORTABLE_FIELDS = {
    "run_id",
    "created_at",
    "started_at",
    "finished_at",
    "duration_seconds",
}

TIMESTAMP_FIELDS = {
    "created_at",
    "started_at",
    "finished_at",
}

MAX_PAGE_SIZE = 100


def get_sort_value(record, sort_by):

    value = record.get(sort_by)

    if value is None:
        return None

    if sort_by in TIMESTAMP_FIELDS:

        if not isinstance(value, str):
            raise ValueError(
                "Invalid history timestamp"
            )

        parsed = datetime.fromisoformat(value)

        if (
            parsed.tzinfo is None
            or parsed.utcoffset() is None
        ):
            raise ValueError(
                "Timezone-aware timestamp required"
            )

        return parsed.astimezone(
            timezone.utc
        ).timestamp()

    if sort_by == "duration_seconds":

        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError(
                "Invalid execution duration"
            )

        return float(value)

    return value


# =====================================================
# FILTER, SORT AND PAGINATE HISTORY
# =====================================================

def query_run_history(
    overview,
    *,
    status=None,
    scenario=None,
    sort_by="started_at",
    order="desc",
    page=1,
    page_size=20,
):

    if (
        not isinstance(overview, dict)
        or not isinstance(overview.get("runs"), list)
        or type(overview.get("total")) is not int
        or overview["total"] != len(overview["runs"])
    ):
        raise ValueError(
            "Invalid history overview"
        )

    # ==========================================
    # VALIDATE QUERY PARAMETERS
    # ==========================================

    if status is not None:
        if status not in VALID_STATUSES:
            raise ValueError(
                "Unsupported execution status"
            )

    if scenario is not None:
        supported = get_supported_scenarios()

        if scenario not in supported:
            raise ValueError(
                "Unsupported simulation scenario"
            )

    if sort_by not in SORTABLE_FIELDS:
        raise ValueError(
            "Unsupported sorting field"
        )

    if order not in {"asc", "desc"}:
        raise ValueError(
            "Sorting order must be asc or desc"
        )

    if type(page) is not int or page < 1:
        raise ValueError(
            "Page must be a positive integer"
        )

    if (
        type(page_size) is not int
        or not 1 <= page_size <= MAX_PAGE_SIZE
    ):
        raise ValueError(
            "Invalid page size"
        )

    # ==========================================
    # FILTER THE HISTORY
    # ==========================================

    filtered = [
        record
        for record in overview["runs"]
        if (
            (status is None or record["status"] == status)
            and (
                scenario is None
                or record["scenario"] == scenario
            )
        )
    ]

    # ==========================================
    # SORT THE HISTORY
    # ==========================================

    # The run ID is our deterministic tie-breaker.
    records = sorted(
        filtered,
        key=lambda item: item["run_id"],
    )

    with_values = []
    without_values = []

    for record in records:

        value = get_sort_value(
            record,
            sort_by,
        )

        if value is None:
            without_values.append(record)
        else:
            with_values.append(
                (value, record)
            )

    with_values.sort(
        key=lambda item: item[0],
        reverse=(order == "desc"),
    )

    # Missing timestamp/duration values stay last,
    # regardless of the requested sort direction.
    ordered = [
        record
        for _, record in with_values
    ] + without_values

    # ==========================================
    # PAGINATION
    # ==========================================

    filtered_total = len(ordered)

    total_pages = math.ceil(
        filtered_total / page_size
    )

    start = (page - 1) * page_size
    end = start + page_size

    page_records = ordered[start:end]

    return {
        "total_runs": overview["total"],
        "filtered_total": filtered_total,
        "status_counts": dict(
            overview["status_counts"]
        ),
        "scenario_counts": dict(
            overview["scenario_counts"]
        ),
        "filters": {
            "status": status,
            "scenario": scenario,
        },
        "sort": {
            "by": sort_by,
            "order": order,
        },
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_previous": (
                page > 1 and total_pages > 0
            ),
            "has_next": page < total_pages,
        },
        "runs": page_records,
    }


# =====================================================
# PUBLIC SERVICE ENTRY POINT
# =====================================================

def get_run_history_page(
    *,
    status=None,
    scenario=None,
    sort_by="started_at",
    order="desc",
    page=1,
    page_size=20,
):

    overview = get_enhanced_run_history()

    return query_run_history(
        overview,
        status=status,
        scenario=scenario,
        sort_by=sort_by,
        order=order,
        page=page,
        page_size=page_size,
    )
