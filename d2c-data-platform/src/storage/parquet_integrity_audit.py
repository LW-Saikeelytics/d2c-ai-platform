
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from src.layers.raw_layer import RawLayerIngestor
from src.storage.parquet_analytics import ParquetAnalyticsWriter
from src.storage.partitioned_events import PartitionedEvents
from src.storage.partitioned_transactions import PartitionedTransactions
from src.storage.remaining_processed_parquet import (
    RemainingProcessedParquet,
    SCHEMAS as CORE_SCHEMAS,
)


ROOT = Path(__file__).resolve().parents[2]

DAY_PARTITIONING = ds.partitioning(
    pa.schema([("simulation_day", pa.int64())]),
    flavor="hive"
)


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def partition_rows(path, columns):
    dataset = ds.dataset(
        path,
        format="parquet",
        partitioning=DAY_PARTITIONING
    )
    return dataset.to_table(columns=columns).to_pylist()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run_audit():

    # ==========================================
    # 1. VERIFY ALL EXISTING STORAGE OUTPUTS
    # ==========================================

    raw = RawLayerIngestor()
    raw_manifest = raw.verify_snapshot(
        raw.build_file_manifest(
            raw.discover_sources()
        )
    )

    analytics = ParquetAnalyticsWriter()
    analytics_stats, analytics_hashes = (
        analytics.source_metadata()
    )
    analytics_result = analytics.verify_existing(
        analytics_stats,
        analytics_hashes
    )

    events_writer = PartitionedEvents()
    event_manifest = load_json(
        events_writer.target / "_partition_manifest.json"
    )

    require(
        event_manifest["run_id"] == raw.run_id,
        "Event partition run mismatch"
    )
    require(
        event_manifest["source_sha256"]
        == events_writer.fingerprint(events_writer.source),
        "Event partition source mismatch"
    )

    event_result = events_writer.verify_output(
        events_writer.target,
        event_manifest
    )

    transactions = PartitionedTransactions()
    transaction_results = {}

    for name in ("orders", "behavior_history"):
        source_hash = transactions.fingerprint(
            transactions.source_dir / f"{name}.jsonl"
        )
        transaction_results[name] = transactions.verify(
            name,
            transactions.output_root / name,
            source_hash
        )

    core = RemainingProcessedParquet()
    core_hashes = {
        name: core.fingerprint(core.source_path(name))
        for name in CORE_SCHEMAS
    }
    core_result = core.verify(
        core.target,
        core_hashes
    )

    run_ids = {
        raw.run_id,
        analytics.run_id,
        events_writer.run_id,
        transactions.run_id,
        core.run_id
    }
    require(len(run_ids) == 1, "Run IDs differ")

    # ==========================================
    # 2. READ THE PARTITIONED PARQUET DATASETS
    # ==========================================

    orders = partition_rows(
        transactions.output_root / "orders",
        [
            "simulation_day",
            "order_id",
            "customer_id",
            "product_id",
            "gross_amount"
        ]
    )

    behaviors = partition_rows(
        transactions.output_root / "behavior_history",
        ["simulation_day", "event_id"]
    )

    events = partition_rows(
        events_writer.target,
        [
            "simulation_day",
            "event_id",
            "event_type",
            "order_id",
            "customer_id",
            "product_id"
        ]
    )

    conversions = partition_rows(
        core.target / "conversion_history",
        ["simulation_day", "result_json"]
    )

    clean_daily = pq.read_table(
        core.target / "daily_metrics_cleaned.parquet"
    ).to_pylist()

    analytics_daily = pq.read_table(
        analytics.target / "daily_business_metrics.parquet"
    ).to_pylist()

    # ==========================================
    # 3. AGGREGATE INDEPENDENTLY BY DAY
    # ==========================================

    order_counts = Counter()
    order_revenue = defaultdict(
        lambda: Decimal("0.00")
    )
    orders_by_id = {}

    for row in orders:
        day = row["simulation_day"]
        order_id = row["order_id"]

        require(
            order_id not in orders_by_id,
            f"Duplicate Parquet order: {order_id}"
        )

        orders_by_id[order_id] = row
        order_counts[day] += 1
        order_revenue[day] += row["gross_amount"]

    behavior_counts = Counter()
    behavior_ids = set()

    for row in behaviors:
        day = row["simulation_day"]
        event_id = row["event_id"]

        require(
            event_id not in behavior_ids,
            f"Duplicate behavior event: {event_id}"
        )

        behavior_ids.add(event_id)
        behavior_counts[day] += 1

    event_counts = Counter()
    purchase_counts = Counter()
    non_purchase_ids = set()
    purchase_order_ids = set()
    all_event_ids = set()

    for row in events:
        day = row["simulation_day"]
        event_id = row["event_id"]

        require(
            event_id not in all_event_ids,
            f"Duplicate Parquet event: {event_id}"
        )

        all_event_ids.add(event_id)
        event_counts[day] += 1

        if row["event_type"] == "purchase":
            order_id = row["order_id"]

            require(
                order_id in orders_by_id,
                f"Purchase has no valid order: {order_id}"
            )
            require(
                order_id not in purchase_order_ids,
                f"Duplicate purchase order: {order_id}"
            )

            order = orders_by_id[order_id]

            require(
                row["simulation_day"]
                == order["simulation_day"]
                and row["customer_id"]
                == order["customer_id"]
                and row["product_id"]
                == order["product_id"],
                f"Purchase/order details differ: {order_id}"
            )

            purchase_order_ids.add(order_id)
            purchase_counts[day] += 1

        else:
            require(
                row["order_id"] is None,
                f"Unexpected order ID: {event_id}"
            )
            non_purchase_ids.add(event_id)

    require(
        purchase_order_ids == set(orders_by_id),
        "Orders and purchase events do not match"
    )
    require(
        non_purchase_ids == behavior_ids,
        "Behavior history and events do not match"
    )

    conversion_counts = Counter()
    converted_counts = Counter()

    for row in conversions:
        day = row["simulation_day"]
        result = json.loads(row["result_json"])

        require(
            type(result.get("converted")) is bool,
            f"Invalid conversion result on day {day}"
        )

        conversion_counts[day] += 1

        if result["converted"]:
            converted_counts[day] += 1

    # ==========================================
    # 4. VALIDATE ALL 90 DAYS
    # ==========================================

    daily_by_day = {
        row["simulation_day"]: row
        for row in clean_daily
    }

    analytics_by_day = {
        row["simulation_day"]: row
        for row in analytics_daily
    }

    days = set(range(1, 91))

    require(
        len(clean_daily) == 90
        and set(daily_by_day) == days,
        "Invalid cleaned daily coverage"
    )
    require(
        len(analytics_daily) == 90
        and set(analytics_by_day) == days,
        "Invalid analytics daily coverage"
    )

    for counts in (
        order_counts,
        behavior_counts,
        event_counts,
        purchase_counts,
        conversion_counts,
        converted_counts
    ):
        require(
            set(counts).issubset(days),
            "Activity found outside days 1-90"
        )

    for day in sorted(days):

        cleaned = daily_by_day[day]
        business = analytics_by_day[day]

        expected = {
            "clean_order_count": order_counts[day],
            "behavior_event_count": behavior_counts[day],
            "clean_event_count": event_counts[day],
            "clean_purchase_event_count":
                purchase_counts[day],
            "conversion_decisions_evaluated":
                conversion_counts[day],
            "historical_converted_decisions":
                converted_counts[day]
        }

        for column, count in expected.items():
            require(
                cleaned[column] == count,
                f"Cleaned metric mismatch: "
                f"day {day}, {column}"
            )

        business_checks = {
            "order_count": order_counts[day],
            "behavior_event_count": behavior_counts[day],
            "total_event_count": event_counts[day],
            "purchase_event_count": purchase_counts[day],
            "historical_converted_decisions":
                converted_counts[day]
        }

        for column, count in business_checks.items():
            require(
                business[column] == count,
                f"Analytics metric mismatch: "
                f"day {day}, {column}"
            )

        require(
            business["gross_revenue"]
            == order_revenue[day],
            f"Revenue mismatch on day {day}"
        )

    # ==========================================
    # 5. VERIFY OVERALL TOTALS
    # ==========================================

    revenue = sum(
        order_revenue.values(),
        Decimal("0.00")
    )

    require(
        len(orders) == analytics_result["clean_orders"],
        "Analytics order total mismatch"
    )
    require(
        len(events) == analytics_result["clean_events"],
        "Analytics event total mismatch"
    )
    require(
        revenue
        == Decimal(analytics_result["gross_revenue"])
        == Decimal(core_result["customer_revenue"]),
        "Cross-layer revenue mismatch"
    )
    require(
        sum(converted_counts.values())
        == analytics_result["historical_conversions"]
        == core_result["historical_conversions"],
        "Historical conversion total mismatch"
    )
    require(
        event_result["events"] == len(events),
        "Event partition total mismatch"
    )
    require(
        transaction_results["orders"]["rows"]
        == len(orders),
        "Order partition total mismatch"
    )
    require(
        transaction_results["behavior_history"]["rows"]
        == len(behaviors),
        "Behavior partition total mismatch"
    )

    # ==========================================
    # 6. SAVE VALIDATION REPORT
    # ==========================================

    analytics_manifest = load_json(
        analytics.target / "_parquet_manifest.json"
    )
    core_manifest = load_json(
        core.target / "_parquet_manifest.json"
    )

    parquet_file_count = (
        len(analytics_manifest["files"])
        + len(event_manifest["partitions"])
        + sum(
            len(load_json(
                transactions.output_root
                / name
                / "_partition_manifest.json"
            )["files"])
            for name in ("orders", "behavior_history")
        )
        + len(core_manifest["files"])
    )

    report = {
        "run_id": raw.run_id,
        "status": "PASSED",
        "raw_source_files_verified":
            raw_manifest["file_count"],
        "parquet_files_verified": parquet_file_count,
        "daily_reconciliation_days": 90,
        "clean_orders": len(orders),
        "clean_behavior_events": len(behaviors),
        "clean_events": len(events),
        "purchase_events": sum(purchase_counts.values()),
        "conversion_decisions": len(conversions),
        "historical_conversions":
            sum(converted_counts.values()),
        "gross_revenue_inr": str(revenue),
        "day_30": {
            "orders": order_counts[30],
            "behavior_events": behavior_counts[30],
            "total_events": event_counts[30],
            "conversion_decisions":
                conversion_counts[30]
        }
    }

    output = (
        ROOT / "reports"
        / "parquet_integrity_report.json"
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with output.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    return report, output


if __name__ == "__main__":

    print("=" * 70)
    print("PHASE 8 - FINAL PARQUET INTEGRITY AUDIT")
    print("=" * 70)

    report, output = run_audit()

    for key, value in report.items():

        if key == "day_30":
            print("\nDAY 30 RECONCILIATION:")
            for name, count in value.items():
                print(f"{name}: {count}")
        else:
            print(f"{key}: {value}")

    print("\nReport:")
    print(output)

    print("\nFINAL PARQUET INTEGRITY AUDIT PASSED.")