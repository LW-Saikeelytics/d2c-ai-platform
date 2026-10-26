
import csv
import math

from decimal import Decimal, InvalidOperation
from pathlib import Path

from src.services.dataset_download_service import (
    resolve_dataset_download,
)

from src.services.run_metric_trends import (
    get_run_metric_trends,
)

# =====================================================
# PHASE 9.8.2A - BUSINESS METRICS SERVICE
# =====================================================

class MetricsDataError(RuntimeError):
    """Metrics data is missing, malformed or inconsistent."""


# Exact schemas discovered from Phase 6 analytics.
# Each group specifies:
# (CSV prefix, integer columns, decimal columns)

METRIC_SCHEMAS = {
    "summary": {
        "dataset_id": "analytics__business_kpi_summary.csv",
        "groups": {
            "customers": (
                "customer_metrics_",
                (
                    "total_customers",
                    "customers_with_orders",
                    "customers_without_orders",
                ),
                (
                    "customer_purchase_rate",
                    "average_orders_per_customer",
                ),
            ),
            "orders": (
                "order_metrics_",
                (
                    "total_orders",
                    "total_units_sold",
                ),
                (
                    "average_order_value",
                    "average_units_per_order",
                    "minimum_order_value",
                    "maximum_order_value",
                ),
            ),
            "conversions": (
                "conversion_metrics_",
                (
                    "conversion_evaluations",
                    "successful_conversions",
                ),
                ("conversion_rate",),
            ),
            "revenue": (
                "revenue_metrics_",
                (),
                (
                    "total_revenue",
                    "average_daily_revenue",
                    "revenue_per_customer",
                    "revenue_per_purchasing_customer",
                ),
            ),
        },
    },
    "funnel": {
        "dataset_id": "analytics__funnel_summary.csv",
        "groups": {
            "events": (
                "event_counts_",
                (
                    "product_views",
                    "add_to_cart",
                    "purchase_intent",
                    "cart_abandonment",
                    "purchases",
                ),
                (),
            ),
            "customer_stages": (
                "customer_stages_",
                (
                    "viewers",
                    "cart_customers",
                    "intent_customers",
                    "purchasing_customers",
                    "customers_with_abandonment",
                ),
                (),
            ),
            "rates": (
                "funnel_rates_",
                (),
                (
                    "view_to_cart_rate",
                    "cart_to_intent_rate",
                    "view_to_purchase_rate",
                    "cart_to_purchase_rate",
                    "intent_to_purchase_rate",
                    "cart_abandonment_signal_rate",
                ),
            ),
        },
    },
}


# =====================================================
# PARSE NUMERIC VALUES
# =====================================================

def parse_metric(value, numeric_type, column):

    try:
        number = Decimal(value.strip())

    except (AttributeError, InvalidOperation, ValueError):
        raise MetricsDataError(
            f"Invalid numeric value in {column}"
        ) from None

    if not number.is_finite() or number < 0:
        raise MetricsDataError(
            f"Invalid numeric range in {column}"
        )

    if column.endswith("_rate") and number > 1:
        raise MetricsDataError(
            f"Rate exceeds 1 in {column}"
        )

    if numeric_type == "int":

        if number != number.to_integral_value():
            raise MetricsDataError(
                f"Expected integer in {column}"
            )

        return int(number)

    result = float(number)

    if not math.isfinite(result):
        raise MetricsDataError(
            f"Numeric overflow in {column}"
        )

    return result


# =====================================================
# READ ONE-ROW SUMMARY CSV
# =====================================================

def read_summary_row(file_path, expected_columns):

    file_path = Path(file_path)

    try:

        if file_path.stat().st_size > 1048576:
            raise MetricsDataError(
                "Metrics file exceeds allowed size"
            )

        with file_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:

            reader = csv.DictReader(file)

            if reader.fieldnames != expected_columns:
                raise MetricsDataError(
                    "Analytics CSV schema mismatch"
                )

            first_row = next(reader, None)

            if first_row is None:
                raise MetricsDataError(
                    "Metrics CSV contains no data"
                )

            if next(reader, None) is not None:
                raise MetricsDataError(
                    "Expected exactly one metrics row"
                )

            if any(
                first_row.get(column) is None
                for column in expected_columns
            ):
                raise MetricsDataError(
                    "Metrics row contains missing values"
                )

            return first_row

    except (OSError, UnicodeError, csv.Error) as exc:
        raise MetricsDataError(
            "Unable to read analytics CSV"
        ) from exc


# =====================================================
# BUILD STRUCTURED RUN METRICS
# =====================================================

def get_run_metrics(run_id):

    result = {
        "run_id": run_id,
    }

    for section_name, schema in METRIC_SCHEMAS.items():

        # Use the existing approved-file resolver.
        # It verifies the completed run and file path.

        dataset = resolve_dataset_download(
            run_id,
            schema["dataset_id"],
        )

        expected_columns = []

        for prefix, integers, decimals in (
            schema["groups"].values()
        ):

            expected_columns.extend(
                prefix + name
                for name in integers + decimals
            )

        row = read_summary_row(
            dataset["file_path"],
            expected_columns,
        )

        section = {}

        for group_name, (
            prefix,
            integers,
            decimals,
        ) in schema["groups"].items():

            group = {}

            for name in integers:

                column = prefix + name

                group[name] = parse_metric(
                    row[column],
                    "int",
                    column,
                )

            for name in decimals:

                column = prefix + name

                group[name] = parse_metric(
                    row[column],
                    "decimal",
                    column,
                )

            section[group_name] = group

        result[section_name] = section

    # ==========================================
    # CROSS-FIELD CONSISTENCY CHECKS
    # ==========================================

    customers = result["summary"]["customers"]

    if (
        customers["customers_with_orders"]
        + customers["customers_without_orders"]
        != customers["total_customers"]
    ):
        raise MetricsDataError(
            "Customer totals are inconsistent"
        )

    conversions = result["summary"]["conversions"]

    if (
        conversions["successful_conversions"]
        > conversions["conversion_evaluations"]
    ):
        raise MetricsDataError(
            "Conversion totals are inconsistent"
        )

    # ==========================================
    # INCLUDE DAILY, WEEKLY AND MONTHLY TRENDS
    # ==========================================

    result["trends"] = get_run_metric_trends(
        run_id
    )

    # ==========================================
    # RETURN COMPLETE METRICS RESPONSE
    # ==========================================

    return result