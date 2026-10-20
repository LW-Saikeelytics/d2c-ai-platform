
import json
import hashlib
import shutil
import tempfile

from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from src.layers.raw_layer import RawLayerIngestor


ROOT = Path(__file__).resolve().parents[2]

EVENT_TYPES = {
    "product_view",
    "add_to_cart",
    "purchase_intent",
    "cart_abandonment",
    "purchase"
}


class AnalyticsLayerBuilder:

    def __init__(self):

        self.ingestor = RawLayerIngestor()
        self.run_id = self.ingestor.run_id

        self.processed_dir = (
            ROOT / "data" / "processed"
            / f"run_id={self.run_id}"
        )

        self.target = (
            ROOT / "data" / "analytics"
            / f"run_id={self.run_id}"
            / "business"
        )

    # ==========================================
    # INPUT
    # ==========================================

    def load_jsonl(self, section, filename):

        path = (
            self.processed_dir
            / section
            / f"{filename}.jsonl"
        )

        with path.open(
            "r", encoding="utf-8"
        ) as file:

            return [
                json.loads(line)
                for line in file
                if line.strip()
            ]

    def load_manifest(self, section):

        path = (
            self.processed_dir
            / section
            / "_processed_manifest.json"
        )

        with path.open(
            "r", encoding="utf-8"
        ) as file:
            manifest = json.load(file)

        if manifest["run_id"] != self.run_id:
            raise ValueError(
                f"Run mismatch in {section}"
            )

        return manifest

    # ==========================================
    # AGGREGATION
    # ==========================================

    def build_metrics(
        self,
        products,
        orders,
        events,
        clean_daily
    ):

        product_lookup = {
            row["product_id"]: row
            for row in products
        }

        if len(product_lookup) != len(products):
            raise ValueError("Duplicate product IDs")

        days = {
            row["simulation_day"]: row
            for row in clean_daily
        }

        if sorted(days) != list(range(1, 91)):
            raise ValueError(
                "Expected exactly 90 daily records"
            )

        order_counts = Counter()
        daily_revenue = defaultdict(
            lambda: Decimal("0.00")
        )
        daily_buyers = defaultdict(set)

        product_orders = Counter()
        product_units = Counter()
        product_revenue = defaultdict(
            lambda: Decimal("0.00")
        )
        product_buyers = defaultdict(set)

        order_lookup = {}

        # --------------------------------------
        # AGGREGATE ORDERS
        # --------------------------------------

        for order in orders:

            order_id = order["order_id"]
            day = order["simulation_day"]
            product_id = order["product_id"]
            customer_id = order["customer_id"]

            if order_id in order_lookup:
                raise ValueError(
                    f"Duplicate order: {order_id}"
                )

            if day not in days:
                raise ValueError(
                    f"Invalid order day: {day}"
                )

            if product_id not in product_lookup:
                raise ValueError(
                    f"Unknown order product: {product_id}"
                )

            amount = Decimal(
                str(order["gross_amount"])
            )

            if not amount.is_finite() or amount < 0:
                raise ValueError(
                    f"Invalid order amount: {order_id}"
                )

            if amount != amount.quantize(
                Decimal("0.01")
            ):
                raise ValueError(
                    f"Amount has extra decimal places: {order_id}"
                )

            order_lookup[order_id] = order

            order_counts[day] += 1
            daily_revenue[day] += amount
            daily_buyers[day].add(customer_id)

            product_orders[product_id] += 1
            product_units[product_id] += order["quantity"]
            product_revenue[product_id] += amount
            product_buyers[product_id].add(customer_id)

        # --------------------------------------
        # AGGREGATE EVENTS
        # --------------------------------------

        daily_events = defaultdict(Counter)
        product_events = defaultdict(Counter)

        purchase_event_ids = set()
        purchase_order_ids = set()

        for event in events:

            day = event["simulation_day"]
            product_id = event["product_id"]
            event_type = event["event_type"]
            event_id = event["event_id"]

            if day not in days:
                raise ValueError(
                    f"Invalid event day: {day}"
                )

            if product_id not in product_lookup:
                raise ValueError(
                    f"Unknown event product: {product_id}"
                )

            if event_type not in EVENT_TYPES:
                raise ValueError(
                    f"Unknown event type: {event_type}"
                )

            if event_id in purchase_event_ids:
                raise ValueError(
                    f"Duplicate event ID: {event_id}"
                )

            purchase_event_ids.add(event_id)

            daily_events[day][event_type] += 1
            product_events[product_id][event_type] += 1

            if event_type == "purchase":

                order_id = event["order_id"]

                if order_id in purchase_order_ids:
                    raise ValueError(
                        f"Duplicate purchase event: {order_id}"
                    )

                purchase_order_ids.add(order_id)

                order = order_lookup.get(order_id)

                if order is None:
                    raise ValueError(
                        f"Unmatched purchase event: {order_id}"
                    )

                if any([
                    order["customer_id"]
                    != event["customer_id"],

                    order["product_id"]
                    != event["product_id"],

                    order["simulation_day"]
                    != event["simulation_day"]
                ]):
                    raise ValueError(
                        f"Purchase event mismatch: {order_id}"
                    )

            elif event.get("order_id") is not None:

                raise ValueError(
                    "Non-purchase event has order ID: "
                    f"{event_id}"
                )

        if purchase_order_ids != set(order_lookup):
            raise ValueError(
                "Not every clean order has a purchase event"
            )

        # --------------------------------------
        # DAILY BUSINESS METRICS
        # --------------------------------------

        daily_output = []

        for day in sorted(days):

            source = days[day]
            events_today = daily_events[day]

            purchases = events_today["purchase"]

            total_events = sum(
                events_today.values()
            )

            if (
                order_counts[day]
                != source["clean_order_count"]
                or purchases
                != source["clean_purchase_event_count"]
                or total_events
                != source["clean_event_count"]
            ):
                raise ValueError(
                    f"Daily reconciliation failed: Day {day}"
                )

            behavior_count = (
                total_events - purchases
            )

            if (
                behavior_count
                != source["behavior_event_count"]
            ):
                raise ValueError(
                    f"Behavior mismatch: Day {day}"
                )

            daily_output.append({
                "simulation_day": day,
                "customers": source["customers"],
                "purchasing_customers": len(
                    daily_buyers[day]
                ),
                "behavior_active_customers":
                    source["behavior_active_customers"],
                "order_count": order_counts[day],
                "gross_revenue": str(
                    daily_revenue[day]
                ),
                "product_views":
                    events_today["product_view"],
                "add_to_carts":
                    events_today["add_to_cart"],
                "purchase_intents":
                    events_today["purchase_intent"],
                "cart_abandonments":
                    events_today["cart_abandonment"],
                "behavior_event_count":
                    behavior_count,
                "purchase_event_count":
                    purchases,
                "total_event_count":
                    total_events,
                "historical_converted_decisions":
                    source["historical_converted_decisions"]
            })

        # --------------------------------------
        # PRODUCT PERFORMANCE
        # --------------------------------------

        product_output = []

        for product in sorted(
            products,
            key=lambda row: row["product_id"]
        ):

            product_id = product["product_id"]
            signals = product_events[product_id]

            product_output.append({
                "product_id": product_id,
                "product_name": product["product_name"],
                "category": product["category"],
                "order_count":
                    product_orders[product_id],
                "units_sold":
                    product_units[product_id],
                "gross_revenue": str(
                    product_revenue[product_id]
                ),
                "purchasing_customers": len(
                    product_buyers[product_id]
                ),
                "product_views":
                    signals["product_view"],
                "add_to_carts":
                    signals["add_to_cart"],
                "purchase_intents":
                    signals["purchase_intent"],
                "cart_abandonments":
                    signals["cart_abandonment"],
                "purchase_events":
                    signals["purchase"]
            })

        # --------------------------------------
        # CROSS-TABLE CHECKS
        # --------------------------------------

        total_revenue = sum(
            (Decimal(row["gross_revenue"])
             for row in daily_output),
            Decimal("0.00")
        )

        product_total = sum(
            (Decimal(row["gross_revenue"])
             for row in product_output),
            Decimal("0.00")
        )

        if total_revenue != product_total:
            raise ValueError(
                "Daily/product revenue mismatch"
            )

        if sum(
            row["order_count"]
            for row in product_output
        ) != len(orders):
            raise ValueError(
                "Product order totals do not reconcile"
            )

        if sum(
            row["total_event_count"]
            for row in daily_output
        ) != len(events):
            raise ValueError(
                "Daily event totals do not reconcile"
            )

        stats = {
            "daily_metric_rows": len(daily_output),
            "product_metric_rows": len(product_output),
            "clean_orders": len(orders),
            "clean_events": len(events),
            "total_gross_revenue": str(total_revenue),
            "historical_converted_decisions": sum(
                row["historical_converted_decisions"]
                for row in daily_output
            )
        }

        return daily_output, product_output, stats

    # ==========================================
    # OUTPUT
    # ==========================================

    @staticmethod
    def write_jsonl(path, rows):

        with path.open(
            "w", encoding="utf-8"
        ) as file:

            for row in rows:
                file.write(
                    json.dumps(
                        row,
                        sort_keys=True,
                        ensure_ascii=False
                    ) + "\n"
                )

    @staticmethod
    def fingerprint(path):

        digest = hashlib.sha256()

        with path.open("rb") as file:
            for chunk in iter(
                lambda: file.read(1024 * 1024),
                b""
            ):
                digest.update(chunk)

        return digest.hexdigest()

    def run(self):

        self.ingestor.ingest()

        for section in (
            "transactions", "entities", "activity"
        ):
            self.load_manifest(section)

        if self.target.exists():
            raise FileExistsError(
                f"Analytics output already exists: {self.target}"
            )

        products = self.load_jsonl(
            "entities", "product_master"
        )

        orders = self.load_jsonl(
            "transactions", "orders"
        )

        events = self.load_jsonl(
            "transactions", "events"
        )

        clean_daily = self.load_jsonl(
            "activity", "daily_metrics_cleaned"
        )

        daily, product, stats = self.build_metrics(
            products, orders, events, clean_daily
        )

        # Check customer revenue reconciliation.
        entity_manifest = self.load_manifest("entities")

        expected_revenue = Decimal(
            entity_manifest["statistics"][
                "reconciled_revenue"
            ]
        )

        if (
            Decimal(stats["total_gross_revenue"])
            != expected_revenue
        ):
            raise ValueError(
                "Analytics/customer revenue mismatch"
            )

        self.target.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with tempfile.TemporaryDirectory(
            prefix=".analytics_stage_",
            dir=self.target.parent
        ) as temp_dir:

            stage = Path(temp_dir) / "business"
            stage.mkdir()

            self.write_jsonl(
                stage / "daily_business_metrics.jsonl",
                daily
            )

            self.write_jsonl(
                stage / "product_performance.jsonl",
                product
            )

            manifest = {
                "run_id": self.run_id,
                "transformation_version": "1.0",
                "created_at_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "statistics": stats,
                "revenue_definition": (
                    "Sum of gross_amount from "
                    "valid cleaned orders; INR"
                ),
                "money_storage": (
                    "Decimal-formatted string "
                    "with two decimal places"
                ),
                "conversion_semantics": (
                    "Historical converted decisions "
                    "are not the same as clean purchases"
                )
            }

            with (
                stage / "_analytics_manifest.json"
            ).open(
                "w", encoding="utf-8"
            ) as file:
                json.dump(manifest, file, indent=2)

            try:
                stage.rename(self.target)

            except PermissionError:

                if self.target.exists():
                    raise

                try:
                    shutil.copytree(stage, self.target)

                    for original in stage.iterdir():
                        copied = self.target / original.name

                        if (
                            self.fingerprint(original)
                            != self.fingerprint(copied)
                        ):
                            raise RuntimeError(
                                f"Copy verification failed: "
                                f"{original.name}"
                            )

                except Exception:
                    if self.target.exists():
                        shutil.rmtree(self.target)
                    raise

        return {
            "statistics": stats,
            "output_path": self.target
        }


if __name__ == "__main__":

    print("=" * 70)
    print("PHASE 8 - ANALYTICS LAYER")
    print("=" * 70)

    builder = AnalyticsLayerBuilder()
    result = builder.run()

    print("\nBUSINESS ANALYTICS:")

    for key, value in result["statistics"].items():
        print(f"{key}: {value}")

    print("\nOutput:")
    print(result["output_path"])

    print("\nANALYTICS LAYER TEST PASSED.")