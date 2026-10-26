
from src.runtime.run_workspace import RUN_ID_PATTERN

from src.services.run_history_service import (
    VALID_STATUSES,
    list_run_history,
    validate_timestamp,
)


# =====================================================
# PHASE 9.11.2 - ENHANCED RUN-HISTORY SERVICE
# =====================================================

PUBLIC_FIELDS = (
    "run_id",
    "status",
    "scenario",
    "days",
    "customers",
    "created_at",
    "started_at",
    "finished_at",
    "exit_code",
)


def calculate_duration(record):

    started = validate_timestamp(
        record.get("started_at"),
        "started_at",
    )

    finished = validate_timestamp(
        record.get("finished_at"),
        "finished_at",
    )

    if started is None or finished is None:
        return None

    seconds = (finished - started).total_seconds()

    if seconds < 0:
        raise ValueError(
            "Run finished before it started"
        )

    return round(seconds, 3)


def build_run_links(run_id, status):

    base = f"/api/v1/runs/{run_id}"

    links = {
        "details": base,
    }

    if status == "COMPLETED":

        links.update({
            "datasets": f"{base}/datasets",
            "metrics": f"{base}/metrics",
            "validations": f"{base}/validations",
        })

    return links


# =====================================================
# BUILD READ-ONLY HISTORY OVERVIEW
# =====================================================

def build_history_overview(records):

    if not isinstance(records, list):
        raise ValueError(
            "Run history must be a list"
        )

    status_counts = {
        name: 0
        for name in sorted(VALID_STATUSES)
    }

    scenario_counts = {}
    seen_ids = set()
    public_runs = []

    for record in records:

        if not isinstance(record, dict):
            raise ValueError(
                "Invalid history record"
            )

        run_id = record.get("run_id")
        status = record.get("status")
        scenario = record.get("scenario")

        if (
            not isinstance(run_id, str)
            or not RUN_ID_PATTERN.fullmatch(run_id)
        ):
            raise ValueError("Invalid run ID")

        if run_id in seen_ids:
            raise ValueError("Duplicate run ID")

        seen_ids.add(run_id)

        if status not in VALID_STATUSES:
            raise ValueError(
                "Unknown run status"
            )

        if (
            not isinstance(scenario, str)
            or not scenario
        ):
            raise ValueError(
                "Invalid scenario"
            )

        for field in ("days", "customers"):

            if (
                type(record.get(field)) is not int
                or record[field] <= 0
            ):
                raise ValueError(
                    f"Invalid {field}"
                )

        duration = calculate_duration(record)

        # Keep only approved public fields.
        public_record = {
            field: record.get(field)
            for field in PUBLIC_FIELDS
        }

        public_record["duration_seconds"] = duration

        public_record["links"] = build_run_links(
            run_id,
            status,
        )

        public_runs.append(public_record)

        status_counts[status] += 1

        scenario_counts[scenario] = (
            scenario_counts.get(scenario, 0) + 1
        )

    return {
        "total": len(public_runs),
        "status_counts": status_counts,
        "scenario_counts": dict(
            sorted(scenario_counts.items())
        ),
        "runs": public_runs,
    }


# =====================================================
# READ EXISTING STORED RUN HISTORY
# =====================================================

def get_enhanced_run_history():

    records = list_run_history()

    return build_history_overview(records)
