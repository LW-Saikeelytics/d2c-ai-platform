
from pathlib import Path
from tempfile import TemporaryDirectory

from src.services.run_metrics_service import (
    MetricsDataError,
    get_run_metrics,
    parse_metric,
    read_summary_row,
)


RUN_ID = (
    "api_run_ebaaf56bd9b14c1d9fca1af532387316"
)


def test_run_metrics_service():

    print("=" * 70)
    print("PHASE 9 - BUSINESS METRICS SERVICE")
    print("=" * 70)

    metrics = get_run_metrics(RUN_ID)

    assert metrics["run_id"] == RUN_ID

    print("Completed simulation metrics loaded: PASS")

    summary = metrics["summary"]

    # ==========================================
    # CUSTOMER METRICS
    # ==========================================

    customers = summary["customers"]

    assert customers["total_customers"] == 100
    assert customers["customers_with_orders"] == 3
    assert customers["customers_without_orders"] == 97
    assert customers["customer_purchase_rate"] == 0.03

    print("Customer metrics: PASS")

    # ==========================================
    # ORDER METRICS
    # ==========================================

    orders = summary["orders"]

    assert orders["total_orders"] == 3
    assert orders["total_units_sold"] == 5
    assert orders["average_order_value"] == 11998.33

    print("Order metrics: PASS")

    # ==========================================
    # CONVERSION METRICS
    # ==========================================

    conversions = summary["conversions"]

    assert conversions["conversion_evaluations"] == 48
    assert conversions["successful_conversions"] == 3
    assert conversions["conversion_rate"] == 0.0625

    print("Conversion metrics: PASS")

    # ==========================================
    # REVENUE METRICS
    # ==========================================

    revenue = summary["revenue"]

    assert revenue["total_revenue"] == 35995.0
    assert revenue["average_daily_revenue"] == 5142.14

    print("Revenue metrics: PASS")

    # ==========================================
    # FUNNEL METRICS
    # ==========================================

    funnel = metrics["funnel"]

    assert funnel["events"]["product_views"] == 48
    assert funnel["events"]["add_to_cart"] == 18
    assert funnel["events"]["purchases"] == 3

    print("Funnel event metrics: PASS")

    assert funnel["customer_stages"]["viewers"] == 29
    assert (
        funnel["customer_stages"]["purchasing_customers"]
        == 3
    )

    print("Funnel customer stages: PASS")

    assert funnel["rates"]["view_to_cart_rate"] == 0.4138
    assert funnel["rates"]["intent_to_purchase_rate"] == 0.6

    print("Funnel conversion rates: PASS")

    # ==========================================
    # PUBLIC RESPONSE STRUCTURE
    # ==========================================

    assert set(metrics.keys()) == {
        "run_id",
        "summary",
        "funnel",
        "trends",
    }

    assert set(summary.keys()) == {
        "customers",
        "orders",
        "conversions",
        "revenue",
    }

    assert "file_path" not in str(metrics)
    assert "generated_run_directory" not in str(metrics)

    print("Structured metrics response: PASS")
    print("Internal filesystem paths hidden: PASS")

    # ==========================================
    # VALIDATION TESTS
    # ==========================================

    try:
        get_run_metrics("invalid-run-id")
    except ValueError:
        print("Invalid run ID rejected: PASS")
    else:
        raise AssertionError("Invalid run ID accepted")

    try:
        parse_metric("NaN", "decimal", "conversion_rate")
    except MetricsDataError:
        print("Non-finite metric rejected: PASS")
    else:
        raise AssertionError("NaN metric accepted")

    with TemporaryDirectory() as temporary:

        invalid_csv = Path(temporary) / "invalid.csv"

        invalid_csv.write_text(
            "wrong_column\n100\n",
            encoding="utf-8",
        )

        try:
            read_summary_row(
                invalid_csv,
                ["total_customers"],
            )
        except MetricsDataError:
            print("Incorrect CSV schema rejected: PASS")
        else:
            raise AssertionError("Invalid CSV schema accepted")

    # ==========================================
    # FINAL SUMMARY
    # ==========================================

    print()
    print("=== BUSINESS METRICS SUMMARY ===")
    print("Run ID:", RUN_ID)
    print("Customers:", customers["total_customers"])
    print("Orders:", orders["total_orders"])
    print("Revenue:", revenue["total_revenue"])
    print("Conversion rate:", conversions["conversion_rate"])
    print("Product views:", funnel["events"]["product_views"])

    print()
    print("Generator execution performed: NO")
    print("Existing analytics files modified: NO")
    print("Metrics API endpoint enabled: NO")

    print()
    print("BUSINESS METRICS SERVICE TEST PASSED.")


if __name__ == "__main__":
    test_run_metrics_service()
