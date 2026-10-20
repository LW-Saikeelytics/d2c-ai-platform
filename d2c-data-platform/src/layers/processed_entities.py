
import csv
import hashlib
import json
import shutil
import tempfile

from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from src.layers.raw_layer import RawLayerIngestor
from src.validation.schema_contract_validator import (
    SchemaContractValidator
)


ROOT = Path(__file__).resolve().parents[2]


class ProcessedEntities:

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

        self.target = self.processed_dir / "entities"

    # ==========================================
    # NORMALIZE CUSTOMER AND PRODUCT DATA
    # ==========================================

    def normalize(self, name, row):

        fields = self.validator.schema[name]["fields"]

        if set(row) != set(fields):
            raise ValueError(
                f"Unexpected fields in {name}"
            )

        return {
            column: self.validator.normalize_value(
                row[column], field_type
            )
            for column, field_type in fields.items()
        }

    def load_customers(self):

        path = (
            self.raw_dir / "simulation" / "customers.csv"
        )

        fields = self.validator.schema["customers"]["fields"]

        with path.open(
            "r", encoding="utf-8-sig", newline=""
        ) as file:

            reader = csv.DictReader(file)

            if reader.fieldnames != list(fields):
                raise ValueError("Customer schema mismatch")

            customers = [
                self.normalize("customers", row)
                for row in reader
            ]

        expected = self.validator.config[
            "expected_datasets"
        ]["customers"]

        if len(customers) != expected:
            raise ValueError("Unexpected customer count")

        return customers

    def load_products(self):

        path = (
            self.raw_dir / "reference"
            / "product_master.json"
        )

        with path.open("r", encoding="utf-8") as file:
            source = json.load(file)

        if not isinstance(source, list):
            raise ValueError("Invalid product master")

        products = [
            self.normalize("product_master", row)
            for row in source
        ]

        expected = self.validator.profile[
            "product_master"
        ]["rows"]

        if len(products) != expected:
            raise ValueError("Unexpected product count")

        return products

    def load_clean_orders(self):

        path = (
            self.processed_dir / "transactions"
            / "orders.jsonl"
        )

        manifest_path = (
            self.processed_dir / "transactions"
            / "_processed_manifest.json"
        )

        with manifest_path.open(
            "r", encoding="utf-8"
        ) as file:
            manifest = json.load(file)

        if manifest["run_id"] != self.run_id:
            raise ValueError("Transaction run mismatch")

        with path.open("r", encoding="utf-8") as file:

            orders = [
                json.loads(line)
                for line in file
                if line.strip()
            ]

        expected = manifest["statistics"][
            "orders"
        ]["processed_rows"]

        if len(orders) != expected:
            raise ValueError(
                "Processed order count mismatch"
            )

        return orders

    # ==========================================
    # RECONCILE CUSTOMER PURCHASE HISTORY
    # ==========================================

    def reconcile_customers(
        self, customers, products, orders
    ):

        customer_ids = [
            row["customer_id"] for row in customers
        ]

        product_ids = [
            row["product_id"] for row in products
        ]

        if len(set(customer_ids)) != len(customer_ids):
            raise ValueError("Duplicate customer IDs")

        if len(set(product_ids)) != len(product_ids):
            raise ValueError("Duplicate product IDs")

        customer_set = set(customer_ids)

        product_lookup = {
            row["product_id"]: row for row in products
        }

        counts = Counter()
        spending = defaultdict(lambda: Decimal("0"))
        last_days = {}

        seen_orders = set()

        for order in orders:

            order_id = order["order_id"]
            customer_id = order["customer_id"]
            product_id = order["product_id"]
            day = order["simulation_day"]

            if order_id in seen_orders:
                raise ValueError("Duplicate order ID")

            seen_orders.add(order_id)

            if customer_id not in customer_set:
                raise ValueError(
                    f"Unknown customer: {customer_id}"
                )

            if product_id not in product_lookup:
                raise ValueError(
                    f"Unknown product: {product_id}"
                )

            product = product_lookup[product_id]

            if day < product["launch_day"]:
                raise ValueError(
                    f"Pre-launch order: {order_id}"
                )

            discontinued = product["discontinue_day"]

            if (
                discontinued is not None
                and day > discontinued
            ):
                raise ValueError(
                    f"Discontinued product order: {order_id}"
                )

            counts[customer_id] += 1

            spending[customer_id] += Decimal(
                str(order["gross_amount"])
            )

            last_days[customer_id] = max(
                day,
                last_days.get(customer_id, day)
            )

        adjusted = 0

        for customer in customers:

            customer_id = customer["customer_id"]

            new_count = counts[customer_id]
            new_spend = spending[customer_id]
            new_last_day = last_days.get(customer_id)

            changed = (
                customer["lifetime_orders"] != new_count
                or customer["lifetime_spend"] != new_spend
                or customer["last_order_day"] != new_last_day
            )

            if changed:
                adjusted += 1

            customer["lifetime_orders"] = new_count
            customer["lifetime_spend"] = new_spend
            customer["last_order_day"] = new_last_day

        if sum(
            row["lifetime_orders"] for row in customers
        ) != len(orders):
            raise ValueError(
                "Customer order totals do not reconcile"
            )

        total_revenue = sum(
            (row["lifetime_spend"] for row in customers),
            Decimal("0")
        )

        order_revenue = sum(
            (
                Decimal(str(order["gross_amount"]))
                for order in orders
            ),
            Decimal("0")
        )

        if total_revenue != order_revenue:
            raise ValueError(
                "Customer revenue does not reconcile"
            )

        return {
            "customer_rows": len(customers),
            "product_rows": len(products),
            "clean_order_rows": len(orders),
            "customer_profiles_adjusted": adjusted,
            "reconciled_revenue": str(total_revenue)
        }

    # ==========================================
    # WRITE OUTPUT
    # ==========================================

    @staticmethod
    def write_jsonl(path, records):

        with path.open("w", encoding="utf-8") as file:

            for row in records:

                file.write(
                    json.dumps(
                        row,
                        ensure_ascii=False,
                        sort_keys=True,
                        default=lambda value: (
                            float(value)
                            if isinstance(value, Decimal)
                            else str(value)
                        )
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

        # Confirm original raw snapshot integrity.
        self.ingestor.ingest()

        if self.target.exists():
            raise FileExistsError(
                f"Processed entities already exist: {self.target}"
            )

        customers = self.load_customers()
        products = self.load_products()
        orders = self.load_clean_orders()

        stats = self.reconcile_customers(
            customers, products, orders
        )

        self.processed_dir.mkdir(
            parents=True, exist_ok=True
        )

        with tempfile.TemporaryDirectory(
            prefix=".entities_stage_",
            dir=self.processed_dir
        ) as temp_dir:

            stage = Path(temp_dir) / "entities"
            stage.mkdir()

            self.write_jsonl(
                stage / "customers.jsonl", customers
            )

            self.write_jsonl(
                stage / "product_master.jsonl", products
            )

            manifest = {
                "run_id": self.run_id,
                "transformation_version": "1.0",
                "created_at_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "source": "verified_raw_and_clean_orders",
                "statistics": stats
            }

            with (
                stage / "_processed_manifest.json"
            ).open("w", encoding="utf-8") as file:

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
                                f"Copy verification failed: {original.name}"
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
    print("PHASE 8 - PROCESSED BUSINESS ENTITIES")
    print("=" * 70)

    processor = ProcessedEntities()
    result = processor.run()

    print("\nENTITY RECONCILIATION:")

    for key, value in result["statistics"].items():
        print(f"{key}: {value}")

    print("\nOutput:")
    print(result["output_path"])

    print(
        "\nPROCESSED BUSINESS ENTITIES TEST PASSED."
    )
