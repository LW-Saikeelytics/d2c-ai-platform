
import csv
import json
import tempfile
import shutil
import filecmp

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from src.layers.raw_layer import RawLayerIngestor
from src.validation.schema_contract_validator import (
    SchemaContractValidator
)


ROOT = Path(__file__).resolve().parents[2]


class ProcessedTransactions:

    def __init__(self):

        self.validator = SchemaContractValidator()
        self.raw_ingestor = RawLayerIngestor()

        self.run_id = self.raw_ingestor.run_id

        self.raw_path = (
            self.raw_ingestor.raw_root
            / f"run_id={self.run_id}"
        )

        self.target = (
            ROOT
            / "data"
            / "processed"
            / f"run_id={self.run_id}"
            / "transactions"
        )

        self.schema = self.validator.schema

    # ----------------------------------------------
    # LOAD AND NORMALIZE
    # ----------------------------------------------

    def load_table(self, name, products):

        path = (
            self.raw_path
            / "simulation"
            / f"{name}.csv"
        )

        if not path.is_file():
            raise FileNotFoundError(path)

        fields = self.schema[name]["fields"]

        rows = []
        removed_prelaunch = 0
        removed_discontinued = 0
        original_count = 0

        with path.open(
            "r",
            encoding="utf-8-sig",
            newline=""
        ) as file:

            reader = csv.DictReader(file)

            if reader.fieldnames != list(fields):
                raise ValueError(
                    f"Schema mismatch: {name}"
                )

            for raw_row in reader:

                original_count += 1

                if set(raw_row) != set(fields):
                    raise ValueError(
                        f"Malformed row in {name}"
                    )

                row = {
                    column:
                        self.validator.normalize_value(
                            raw_row[column],
                            field_type
                        )
                    for column, field_type in fields.items()
                }

                product_id = row["product_id"]

                if product_id not in products:
                    raise ValueError(
                        f"Unknown product: {product_id}"
                    )

                product = products[product_id]
                day = row["simulation_day"]

                if day < product["launch_day"]:

                    removed_prelaunch += 1
                    continue

                discontinue_day = product.get(
                    "discontinue_day"
                )

                if (
                    discontinue_day is not None
                    and day > discontinue_day
                ):

                    removed_discontinued += 1
                    continue

                rows.append(row)

        stats = {
            "source_rows": original_count,
            "processed_rows": len(rows),
            "removed_prelaunch": removed_prelaunch,
            "removed_discontinued": removed_discontinued
        }

        return rows, stats

    # ----------------------------------------------
    # REFERENTIAL INTEGRITY
    # ----------------------------------------------

    @staticmethod
    def validate_relationships(
        orders,
        behaviors,
        events
    ):

        order_ids = [
            row["order_id"]
            for row in orders
        ]

        behavior_ids = [
            row["event_id"]
            for row in behaviors
        ]

        event_ids = [
            row["event_id"]
            for row in events
        ]

        if len(set(order_ids)) != len(order_ids):
            raise ValueError("Duplicate order IDs")

        if len(set(behavior_ids)) != len(behavior_ids):
            raise ValueError("Duplicate behavior IDs")

        if len(set(event_ids)) != len(event_ids):
            raise ValueError("Duplicate event IDs")

        non_purchase_ids = {
            row["event_id"]
            for row in events
            if row["event_type"] != "purchase"
        }

        if set(behavior_ids) != non_purchase_ids:
            raise ValueError(
                "Behavior/event relationship mismatch"
            )

        purchase_order_ids = [
            row["order_id"]
            for row in events
            if row["event_type"] == "purchase"
        ]

        if (
            None in purchase_order_ids
            or len(purchase_order_ids)
            != len(set(purchase_order_ids))
            or set(purchase_order_ids)
            != set(order_ids)
        ):
            raise ValueError(
                "Purchase event/order relationship mismatch"
            )

        return {
            "orders_reconciled": len(order_ids),
            "behavior_events_reconciled": len(behavior_ids),
            "purchase_events_reconciled": (
                len(purchase_order_ids)
            )
        }

    # ----------------------------------------------
    # JSONL OUTPUT
    # ----------------------------------------------

    @staticmethod
    def json_default(value):

        if isinstance(value, Decimal):
            return float(value)

        raise TypeError(
            f"Unsupported value: {type(value)}"
        )

    def write_jsonl(self, path, records):

        with path.open(
            "w",
            encoding="utf-8"
        ) as file:

            for record in records:

                file.write(
                    json.dumps(
                        record,
                        default=self.json_default,
                        sort_keys=True,
                        ensure_ascii=False
                    )
                    + "\n"
                )

    # ----------------------------------------------
    # PROCESS
    # ----------------------------------------------

    def run(self):

        # Verify the frozen raw snapshot before use.
        self.raw_ingestor.ingest()

        product_path = (
            self.raw_path
            / "reference"
            / "product_master.json"
        )

        with product_path.open(
            "r",
            encoding="utf-8"
        ) as file:

            products_list = json.load(file)

        products = {
            item["product_id"]: item
            for item in products_list
        }

        if len(products) != len(products_list):
            raise ValueError(
                "Duplicate product IDs in master"
            )

        tables = {}
        statistics = {}

        for name in (
            "orders",
            "behavior_history",
            "events"
        ):

            rows, stats = self.load_table(
                name,
                products
            )

            tables[name] = rows
            statistics[name] = stats

        relationships = self.validate_relationships(
            tables["orders"],
            tables["behavior_history"],
            tables["events"]
        )

        self.target.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if self.target.exists():
            raise FileExistsError(
                "Processed transactions already exist. "
                "Do not overwrite them automatically: "
                f"{self.target}"
            )

        with tempfile.TemporaryDirectory(
            prefix=".transactions_stage_",
            dir=self.target.parent
        ) as temp_dir:

            stage = Path(temp_dir) / "transactions"
            stage.mkdir()

            for name, rows in tables.items():

                self.write_jsonl(
                    stage / f"{name}.jsonl",
                    rows
                )

            manifest = {
                "run_id": self.run_id,
                "transformation_version": "1.0",
                "created_at_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "source": "verified_raw_snapshot",
                "statistics": statistics,
                "relationships": relationships
            }

            with (
                stage / "_processed_manifest.json"
            ).open(
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    manifest,
                    file,
                    indent=2
                )

            try:
                # First attempt an atomic directory rename.
                stage.rename(self.target)

            except PermissionError:
                # Windows / OneDrive fallback:
                # copy the completed files instead.
                try:
                    shutil.copytree(
                        stage,
                        self.target
                    )

                    # Verify every copied file.
                    for source_file in stage.iterdir():

                        target_file = (
                            self.target / source_file.name
                        )

                        if not filecmp.cmp(
                            source_file,
                            target_file,
                            shallow=False
                        ):
                            raise RuntimeError(
                                "Processed file verification "
                                f"failed: {source_file.name}"
                            )

                except Exception:

                    # Clean up incomplete fallback output.
                    if self.target.exists():
                        shutil.rmtree(self.target)

                    raise

        return {
            "statistics": statistics,
            "relationships": relationships,
            "output_path": self.target
        }


if __name__ == "__main__":

    print("=" * 70)
    print("PHASE 8 - PROCESSED TRANSACTIONS")
    print("=" * 70)

    processor = ProcessedTransactions()
    result = processor.run()

    print("\nTRANSACTION CLEANING:")

    for name, stats in result["statistics"].items():

        print(f"\n{name.upper()}")

        for key, value in stats.items():
            print(f"{key}: {value:,}")

    print("\nRELATIONSHIP VALIDATION:")
    print(result["relationships"])

    print("\nOutput:")
    print(result["output_path"])

    print(
        "\nPROCESSED TRANSACTIONS TEST PASSED."
    )
