
import csv
import math

from decimal import Decimal, InvalidOperation
from pathlib import Path

from src.services.dataset_download_service import (
    resolve_dataset_download,
)


# =====================================================
# PHASE 9.8.2B - BUSINESS METRIC TRENDS
# =====================================================

class MetricTrendError(RuntimeError):
    """Trend analytics are missing or invalid."""


TREND_SCHEMAS = {
    "daily": {
        "dataset_id": "analytics__daily_analytics.csv",
        "period": "simulation_day",
        "max_rows": 366,
        "columns": (
            "simulation_day",
            "customers",
            "active_customers",
            "purchasing_customers",
            "events",
            "orders",
            "conversion_rate",
            "revenue",
            "average_order_value",
            "orders_per_customer",
            "events_per_customer",
        ),
        "integers": (
            "simulation_day",
            "customers",
            "active_customers",
            "purchasing_customers",
            "events",
            "orders",
        ),
    },
    "weekly": {
        "dataset_id": "analytics__weekly_analytics.csv",
        "period": "week",
        "max_rows": 60,
        "columns": (
            "week",
            "days",
            "events",
            "orders",
            "revenue",
            "average_daily_orders",
            "average_daily_revenue",
            "average_order_value",
        ),
        "integers": (
            "week",
            "days",
            "events",
            "orders",
        ),
    },
    "monthly": {
        "dataset_id": "analytics__monthly_analytics.csv",
        "period": "simulation_month",
        "max_rows": 24,
        "columns": (
            "simulation_month",
            "days",
            "events",
            "orders",
            "revenue",
            "average_daily_orders",
            "average_daily_revenue",
            "average_order_value",
        ),
        "integers": (
            "simulation_month",
            "days",
            "events",
            "orders",
        ),
    },
}


# =====================================================
# PARSE TREND METRIC VALUES
# =====================================================

def parse_trend_number(value, column, integer=False):

    if not isinstance(value, str) or not value.strip():
        raise MetricTrendError(
            f"Missing metric value in {column}"
        )

    try:
        number = Decimal(value.strip())

    except (InvalidOperation, ValueError):
        raise MetricTrendError(
            f"Invalid metric value in {column}"
        ) from None

    if not number.is_finite() or number < 0:
        raise MetricTrendError(
            f"Invalid numeric range in {column}"
        )

    if column.endswith("_rate") and number > 1:
        raise MetricTrendError(
            f"Rate exceeds 1 in {column}"
        )

    if integer:

        if number != number.to_integral_value():
            raise MetricTrendError(
                f"Expected integer in {column}"
            )

        return int(number)

    result = float(number)

    if not math.isfinite(result):
        raise MetricTrendError(
            f"Numeric overflow in {column}"
        )

    return result


# =====================================================
# READ AND VALIDATE ANALYTICS TREND TABLE
# =====================================================

def read_trend_table(file_path, schema):

    file_path = Path(file_path)

    expected_columns = list(schema["columns"])
    integer_columns = set(schema["integers"])
    period_field = schema["period"]

    rows = []

    try:

        if file_path.stat().st_size > 1048576:
            raise MetricTrendError(
                "Trend file exceeds allowed size"
            )

        with file_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:

            reader = csv.DictReader(file)

            if reader.fieldnames != expected_columns:
                raise MetricTrendError(
                    "Trend analytics schema mismatch"
                )

            for row in reader:

                if len(rows) >= schema["max_rows"]:
                    raise MetricTrendError(
                        "Too many trend records"
                    )

                if None in row:
                    raise MetricTrendError(
                        "Unexpected extra CSV values"
                    )

                parsed = {}

                for column in expected_columns:

                    parsed[column] = parse_trend_number(
                        row.get(column),
                        column,
                        integer=column in integer_columns,
                    )

                # Each trend starts at period 1 and
                # must follow chronological order.

                expected_period = len(rows) + 1

                if parsed[period_field] != expected_period:
                    raise MetricTrendError(
                        "Trend periods are not sequential"
                    )

                rows.append(parsed)

    except (OSError, UnicodeError, csv.Error) as exc:

        raise MetricTrendError(
            "Unable to read trend analytics"
        ) from exc

    if not rows:
        raise MetricTrendError(
            "Trend analytics contain no records"
        )

    return rows


# =====================================================
# BUILD DAILY, WEEKLY AND MONTHLY TRENDS
# =====================================================

def get_run_metric_trends(run_id):

    trends = {}

    for trend_name, schema in TREND_SCHEMAS.items():

        dataset = resolve_dataset_download(
            run_id,
            schema["dataset_id"],
        )

        trends[trend_name] = read_trend_table(
            dataset["file_path"],
            schema,
        )

    return trends
