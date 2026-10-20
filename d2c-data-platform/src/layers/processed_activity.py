
import csv
import hashlib
import json
import shutil
import tempfile

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from src.layers.raw_layer import RawLayerIngestor
from src.validation.schema_contract_validator import (
    SchemaContractValidator
)


ROOT = Path(__file__).resolve().parents[2]


class ProcessedActivity:

    def __init__(self):

        self.validator = SchemaContractValidator()
        self.ingestor = RawLayerIngestor()

        self.run_id = self.ingestor.run_id

        self.raw_dir = (
            self.ingestor.raw_root
            / f"run_id={self.run_id}"
        )

        self.processed_dir = (
            ROOT / "data" / "processed"
            / f"run_id={self.run_id}"
        )

        self.target = self.processed_dir / "activity"

    # ==========================================
    # LOAD SOURCE DATA USING CANONICAL SCHEMA
    # ==========================================

    def load_source(self, name):

        path = (
            self.raw_dir
            / "simulation"
            / f"{name}.csv"
        )

        fields = self.validator.schema[name]["fields"]

        with path.open(
            "r", encoding="utf-8-sig", newline=""
        ) as file:

            reader = csv.DictReader(file)

            if reader.fieldnames != list(fields):
                raise ValueError(
                    f"Schema mismatch: {name}"
                )

            rows = []

            for row in reader:

                if set(row) != set(fields):
                    raise ValueError(
                        f"Malformed record: {name}"
                    )

                rows.append({
                    column:
                        self.validator.normalize_value(
                            row[column], field_type
                        )
                    for column, field_type in fields.items()
                })

        expected = self.validator.config[
            "expected_datasets"
        ][name]

        if len(rows) != expected:
            raise ValueError(
                f"Unexpected row count: {name}"
            )

        return rows

    # ==========================================
    # LOAD ALREADY PROCESSED DATA
    # ==========================================

    def load_processed(self, section, name):

        path = (
            self.processed_dir
            / section
            / f"{name}.jsonl"
        )

        with path.open(
            "r", encoding="utf-8"
        ) as file:

            return [
                json.loads(line)
                for line in file
                if line.strip()
            ]

    # ==========================================
    # BUILD CLEANED DAILY METRICS
    # ==========================================

    def build_daily_metrics(
        self,
        customers,
        orders,
        behaviors,
        events,
        conversions,
        original_daily
    ):

        order_counts = Counter()
        behavior_counts = Counter()
        event_counts = Counter()
        purchase_counts = Counter()

        active_customers = defaultdict(set)

        evaluated_counts = Counter()
        historical_converted = Counter()

        for order in orders:
            order_counts[order["simulation_day"]] += 1

        for behavior in behaviors:

            day = behavior["simulation_day"]

            behavior_counts[day] += 1

            active_customers[day].add(
                behavior["customer_id"]
            )

        for event in events:

            day = event["simulation_day"]

            event_counts[day] += 1

            if event["event_type"] == "purchase":
                purchase_counts[day] += 1

        seen_decisions = set()

        for record in conversions:

            day = record["simulation_day"]

            key = (
                day,
                record["customer_id"]
            )

            if key in seen_decisions:
                raise ValueError(
                    f"Duplicate conversion record: {key}"
                )

            seen_decisions.add(key)

            result = record["result"]

            if not isinstance(
                result.get("converted"), bool
            ):
                raise ValueError(
                    f"Invalid conversion decision: {key}"
                )

            evaluated_counts[day] += 1

            if result["converted"]:
                historical_converted[day] += 1

        days = [
            row["simulation_day"]
            for row in original_daily
        ]

        expected_days = list(
            range(1, len(original_daily) + 1)
        )

        if sorted(days) != expected_days:
            raise ValueError(
                "Daily metrics must cover consecutive "
                "simulation days exactly once."
            )

        cleaned = []

        for original in sorted(
            original_daily,
            key=lambda row: row["simulation_day"]
        ):

            day = original["simulation_day"]

            # Verify the original conversion summary
            # against individual historical decisions.
            original_conversion = original["conversion"]

            if (
                original_conversion["customers_evaluated"]
                != evaluated_counts[day]
            ):
                raise ValueError(
                    f"Conversion evaluation mismatch: Day {day}"
                )

            if (
                original_conversion["conversions"]
                != historical_converted[day]
            ):
                raise ValueError(
                    f"Historical conversion mismatch: Day {day}"
                )

            # Clean purchase events must represent
            # exactly the same orders as the clean
            # order table.
            if (
                purchase_counts[day]
                != order_counts[day]
            ):
                raise ValueError(
                    f"Order/purchase mismatch: Day {day}"
                )

            if (
                event_counts[day]
                != behavior_counts[day]
                + purchase_counts[day]
            ):
                raise ValueError(
                    f"Behavior/event mismatch: Day {day}"
                )

            cleaned.append({
                "simulation_day": day,
                "customers": len(customers),

                "behavior_event_count":
                    behavior_counts[day],

                "behavior_active_customers":
                    len(active_customers[day]),

                "conversion_decisions_evaluated":
                    evaluated_counts[day],

                "historical_converted_decisions":
                    historical_converted[day],

                "clean_order_count":
                    order_counts[day],

                "clean_purchase_event_count":
                    purchase_counts[day],

                "clean_event_count":
                    event_counts[day]
            })

        if sum(order_counts.values()) != len(orders):
            raise ValueError("Order count did not reconcile")

        if sum(behavior_counts.values()) != len(behaviors):
            raise ValueError("Behavior count did not reconcile")

        if sum(event_counts.values()) != len(events):
            raise ValueError("Event count did not reconcile")

        if sum(evaluated_counts.values()) != len(conversions):
            raise ValueError(
                "Conversion history count did not reconcile"
            )

        return cleaned, {
            "customers": len(customers),
            "conversion_history_rows": len(conversions),
            "original_daily_metric_days": len(original_daily),
            "clean_daily_metric_days": len(cleaned),
            "clean_orders": len(orders),
            "clean_behavior_events": len(behaviors),
            "clean_events": len(events),
            "clean_purchase_events": sum(
                purchase_counts.values()
            ),
            "historical_converted_decisions": sum(
                historical_converted.values()
            )
        }

    # ==========================================
    # OUTPUT HELPERS
    # ==========================================

    @staticmethod
    def write_jsonl(path, records):

        with path.open(
            "w", encoding="utf-8"
        ) as file:

            for row in records:

                file.write(
                    json.dumps(
                        row,
                        ensure_ascii=False,
                        sort_keys=True
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

    # ==========================================
    # RUN
    # ==========================================

    def run(self):

        self.ingestor.ingest()

        if self.target.exists():
            raise FileExistsError(
                f"Activity output already exists: {self.target}"
            )

        conversions = self.load_source(
            "conversion_history"
        )

        original_daily = self.load_source(
            "daily_metrics"
        )

        customers = self.load_processed(
            "entities", "customers"
        )

        orders = self.load_processed(
            "transactions", "orders"
        )

        behaviors = self.load_processed(
            "transactions", "behavior_history"
        )

        events = self.load_processed(
            "transactions", "events"
        )

        cleaned_daily, stats = self.build_daily_metrics(
            customers,
            orders,
            behaviors,
            events,
            conversions,
            original_daily
        )

        self.processed_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        with tempfile.TemporaryDirectory(
            prefix=".activity_stage_",
            dir=self.processed_dir
        ) as temp_dir:

            stage = Path(temp_dir) / "activity"
            stage.mkdir()

            self.write_jsonl(
                stage / "conversion_history.jsonl",
                conversions
            )

            self.write_jsonl(
                stage / "daily_metrics_source.jsonl",
                original_daily
            )

            self.write_jsonl(
                stage / "daily_metrics_cleaned.jsonl",
                cleaned_daily
            )

            manifest = {
                "run_id": self.run_id,
                "transformation_version": "1.0",
                "created_at_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "statistics": stats,
                "semantics": {
                    "conversion_history":
                        "Original historical simulation decisions",
                    "daily_metrics_source":
                        "Original simulation daily summaries",
                    "daily_metrics_cleaned":
                        "Recomputed from cleaned transactions; "
                        "historical conversion decisions retained "
                        "as a separate measure"
                }
            }

            with (
                stage / "_processed_manifest.json"
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
    print("PHASE 8 - PROCESSED ACTIVITY AND DAILY METRICS")
    print("=" * 70)

    processor = ProcessedActivity()
    result = processor.run()

    print("\nACTIVITY RECONCILIATION:")

    for key, value in result["statistics"].items():
        print(f"{key}: {value:,}")

    print("\nOutput:")
    print(result["output_path"])

    print(
        "\nPROCESSED ACTIVITY TEST PASSED."
    )
