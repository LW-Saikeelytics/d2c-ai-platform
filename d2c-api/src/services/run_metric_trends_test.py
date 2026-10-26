
from pathlib import Path
from tempfile import TemporaryDirectory

from src.services.run_metric_trends import (
    TREND_SCHEMAS,
    MetricTrendError,
    get_run_metric_trends,
    read_trend_table,
    parse_trend_number,
)

from src.services.run_metrics_service import (
    get_run_metrics,
)


RUN_ID = (
    "api_run_ebaaf56bd9b14c1d9fca1af532387316"
)


def test_metric_trends():

    print("=" * 70)
    print("PHASE 9 - BUSINESS METRIC TRENDS")
    print("=" * 70)

    trends = get_run_metric_trends(RUN_ID)

    assert set(trends.keys()) == {
        "daily",
        "weekly",
        "monthly",
    }

    print("Daily, weekly and monthly tables loaded: PASS")

    daily = trends["daily"]
    weekly = trends["weekly"]
    monthly = trends["monthly"]

    # ==========================================
    # TEST 1 - DAILY ANALYTICS
    # ==========================================

    assert len(daily) == 7

    assert [
        row["simulation_day"]
        for row in daily
    ] == list(range(1, 8))

    print("Seven simulation days loaded: PASS")

    assert daily[0]["customers"] == 100
    assert daily[0]["orders"] == 1
    assert daily[0]["revenue"] == 23999.0

    print("Day 1 business metrics: PASS")

    assert sum(
        row["orders"] for row in daily
    ) == 3

    assert sum(
        row["events"] for row in daily
    ) == 87

    assert abs(
        sum(row["revenue"] for row in daily)
        - 35995.0
    ) < 0.01

    print("Daily totals reconciled: PASS")

    # ==========================================
    # TEST 2 - WEEKLY ANALYTICS
    # ==========================================

    assert len(weekly) == 1
    assert weekly[0]["week"] == 1
    assert weekly[0]["days"] == 7
    assert weekly[0]["orders"] == 3
    assert weekly[0]["events"] == 87
    assert weekly[0]["revenue"] == 35995.0

    print("Weekly metrics verified: PASS")

    # ==========================================
    # TEST 3 - MONTHLY ANALYTICS
    # ==========================================

    assert len(monthly) == 1
    assert monthly[0]["simulation_month"] == 1
    assert monthly[0]["days"] == 7
    assert monthly[0]["orders"] == 3
    assert monthly[0]["revenue"] == 35995.0

    print("Monthly metrics verified: PASS")

    # ==========================================
    # TEST 4 - INTEGRATED METRICS RESPONSE
    # ==========================================

    metrics = get_run_metrics(RUN_ID)

    assert metrics["trends"] == trends

    assert (
        metrics["summary"]["orders"]["total_orders"]
        == sum(row["orders"] for row in daily)
    )

    assert (
        metrics["summary"]["revenue"]["total_revenue"]
        == sum(row["revenue"] for row in daily)
    )

    print("Summary and trends integrated: PASS")

    # ==========================================
    # TEST 5 - BAD METRIC VALUES
    # ==========================================

    for value in ("NaN", "-1", "Infinity", ""):

        try:
            parse_trend_number(
                value,
                "revenue",
            )

        except MetricTrendError:
            pass

        else:
            raise AssertionError(
                f"Invalid metric accepted: {value}"
            )

    print("Invalid numeric metrics rejected: PASS")

    # ==========================================
    # TEST 6 - CORRUPTED CSV SCHEMAS
    # ==========================================

    with TemporaryDirectory() as temporary:

        path = Path(temporary) / "invalid.csv"

        path.write_text(
            "wrong_column\n1\n",
            encoding="utf-8",
        )

        try:
            read_trend_table(
                path,
                TREND_SCHEMAS["daily"],
            )

        except MetricTrendError:
            print("Incorrect trend schema rejected: PASS")

        else:
            raise AssertionError(
                "Incorrect trend schema accepted"
            )

        # Correct columns but an invalid period.
        schema = TREND_SCHEMAS["daily"]

        columns = list(schema["columns"])

        values = [
            "2" if name == "simulation_day" else "0"
            for name in columns
        ]

        path.write_text(
            ",".join(columns)
            + "\n"
            + ",".join(values)
            + "\n",
            encoding="utf-8",
        )

        try:
            read_trend_table(
                path,
                schema,
            )

        except MetricTrendError:
            print("Nonsequential trend period rejected: PASS")

        else:
            raise AssertionError(
                "Invalid period accepted"
            )

    # ==========================================
    # TEST 7 - INVALID RUN IDENTIFIER
    # ==========================================

    try:
        get_run_metric_trends("invalid-run-id")

    except ValueError:
        print("Invalid run ID rejected: PASS")

    else:
        raise AssertionError(
            "Invalid run ID accepted"
        )

    # ==========================================
    # FINAL SUMMARY
    # ==========================================

    print()
    print("=== BUSINESS METRIC TRENDS ===")
    print("Simulation days:", len(daily))
    print("Weekly records:", len(weekly))
    print("Monthly records:", len(monthly))
    print("Total events:", sum(
        row["events"] for row in daily
    ))
    print("Total orders:", sum(
        row["orders"] for row in daily
    ))
    print("Total revenue:", sum(
        row["revenue"] for row in daily
    ))

    print()
    print("Generator execution performed: NO")
    print("Existing analytics files modified: NO")
    print("Metrics HTTP endpoint enabled: NO")

    print()
    print("BUSINESS METRIC TRENDS TEST PASSED.")


if __name__ == "__main__":
    test_metric_trends()