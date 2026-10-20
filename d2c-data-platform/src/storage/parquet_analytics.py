
import hashlib
import json
import shutil
import tempfile

from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[2]

INT = pa.int64()
TEXT = pa.string()
MONEY = pa.decimal128(18, 2)


SCHEMAS = {
    "daily_business_metrics": pa.schema([
        ("simulation_day", INT),
        ("customers", INT),
        ("purchasing_customers", INT),
        ("behavior_active_customers", INT),
        ("order_count", INT),
        ("gross_revenue", MONEY),
        ("product_views", INT),
        ("add_to_carts", INT),
        ("purchase_intents", INT),
        ("cart_abandonments", INT),
        ("behavior_event_count", INT),
        ("purchase_event_count", INT),
        ("total_event_count", INT),
        ("historical_converted_decisions", INT),
    ]),

    "product_performance": pa.schema([
        ("product_id", TEXT),
        ("product_name", TEXT),
        ("category", TEXT),
        ("order_count", INT),
        ("units_sold", INT),
        ("gross_revenue", MONEY),
        ("purchasing_customers", INT),
        ("product_views", INT),
        ("add_to_carts", INT),
        ("purchase_intents", INT),
        ("cart_abandonments", INT),
        ("purchase_events", INT),
    ])
}


class ParquetAnalyticsWriter:

    def __init__(self):

        config_path = (
            ROOT / "config" / "platform_config.json"
        )

        with config_path.open(
            "r", encoding="utf-8"
        ) as file:
            config = json.load(file)

        self.run_id = config["source"]["run_id"]

        self.source = (
            ROOT / "data" / "analytics"
            / f"run_id={self.run_id}"
            / "business"
        )

        self.target = (
            ROOT / "data" / "parquet"
            / f"run_id={self.run_id}"
            / "analytics"
            / "business"
        )

    # =========================================
    # FINGERPRINT
    # =========================================

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

    # =========================================
    # SOURCE METADATA
    # =========================================

    def source_metadata(self):

        manifest_path = (
            self.source / "_analytics_manifest.json"
        )

        with manifest_path.open(
            "r", encoding="utf-8"
        ) as file:
            manifest = json.load(file)

        if manifest["run_id"] != self.run_id:
            raise ValueError(
                "Analytics source run mismatch"
            )

        source_hashes = {}

        for name in SCHEMAS:

            filename = f"{name}.jsonl"

            source_hashes[filename] = (
                self.fingerprint(self.source / filename)
            )

        source_hashes["_analytics_manifest.json"] = (
            self.fingerprint(manifest_path)
        )

        return manifest["statistics"], source_hashes

    # =========================================
    # BUILD TYPED ARROW TABLE
    # =========================================

    def build_table(self, name):

        schema = SCHEMAS[name]
        path = self.source / f"{name}.jsonl"

        records = []

        with path.open(
            "r", encoding="utf-8"
        ) as file:

            for line_number, line in enumerate(
                file, start=1
            ):

                if not line.strip():
                    continue

                record = json.loads(line)

                if set(record) != set(schema.names):
                    raise ValueError(
                        f"Column mismatch in {name}, "
                        f"line {line_number}"
                    )

                amount = Decimal(
                    str(record["gross_revenue"])
                )

                if (
                    not amount.is_finite()
                    or amount < 0
                    or amount != amount.quantize(
                        Decimal("0.01")
                    )
                ):
                    raise ValueError(
                        f"Invalid revenue in {name}, "
                        f"line {line_number}"
                    )

                record["gross_revenue"] = amount
                records.append(record)

        return pa.Table.from_pylist(
            records,
            schema=schema
        )

    # =========================================
    # RECONCILIATION
    # =========================================

    @staticmethod
    def validate_tables(tables, stats):

        daily = tables[
            "daily_business_metrics"
        ].to_pylist()

        product = tables[
            "product_performance"
        ].to_pylist()

        if len(daily) != stats["daily_metric_rows"]:
            raise ValueError(
                "Daily metrics row-count mismatch"
            )

        if len(product) != stats["product_metric_rows"]:
            raise ValueError(
                "Product metrics row-count mismatch"
            )

        daily_revenue = sum(
            (row["gross_revenue"] for row in daily),
            Decimal("0.00")
        )

        product_revenue = sum(
            (row["gross_revenue"] for row in product),
            Decimal("0.00")
        )

        expected_revenue = Decimal(
            str(stats["total_gross_revenue"])
        )

        if not (
            daily_revenue
            == product_revenue
            == expected_revenue
        ):
            raise ValueError(
                "Parquet revenue reconciliation failed"
            )

        for rows in (daily, product):

            if sum(
                row["order_count"] for row in rows
            ) != stats["clean_orders"]:
                raise ValueError(
                    "Parquet order count mismatch"
                )

        if sum(
            row["total_event_count"]
            for row in daily
        ) != stats["clean_events"]:
            raise ValueError(
                "Parquet event count mismatch"
            )

        if sum(
            row["historical_converted_decisions"]
            for row in daily
        ) != stats["historical_converted_decisions"]:
            raise ValueError(
                "Historical conversion mismatch"
            )

        return {
            "daily_rows": len(daily),
            "product_rows": len(product),
            "clean_orders": stats["clean_orders"],
            "clean_events": stats["clean_events"],
            "gross_revenue": str(daily_revenue),
            "historical_conversions":
                stats["historical_converted_decisions"]
        }

    # =========================================
    # VERIFY EXISTING PARQUET
    # =========================================

    def verify_existing(
        self, stats, source_hashes
    ):

        manifest_path = (
            self.target / "_parquet_manifest.json"
        )

        with manifest_path.open(
            "r", encoding="utf-8"
        ) as file:
            manifest = json.load(file)

        if manifest["run_id"] != self.run_id:
            raise ValueError(
                "Existing Parquet run mismatch"
            )

        if manifest["source_hashes"] != source_hashes:
            raise ValueError(
                "Analytics source has changed"
            )

        expected_files = {
            f"{name}.parquet" for name in SCHEMAS
        } | {"_parquet_manifest.json"}

        actual_files = {
            path.name
            for path in self.target.iterdir()
            if path.is_file()
        }

        if actual_files != expected_files:
            raise ValueError(
                "Parquet output inventory mismatch"
            )

        tables = {}

        for name in SCHEMAS:

            filename = f"{name}.parquet"
            path = self.target / filename

            if (
                self.fingerprint(path)
                != manifest["files"][filename]["sha256"]
            ):
                raise ValueError(
                    f"Parquet fingerprint mismatch: {name}"
                )

            table = pq.ParquetFile(path).read()

            if not table.schema.equals(SCHEMAS[name]):
                raise ValueError(
                    f"Parquet schema mismatch: {name}"
                )

            tables[name] = table

        return self.validate_tables(tables, stats)

    # =========================================
    # WRITE PARQUET
    # =========================================

    def run(self):

        stats, source_hashes = (
            self.source_metadata()
        )

        if self.target.exists():

            result = self.verify_existing(
                stats, source_hashes
            )

            return "VERIFIED_EXISTING", result

        tables = {
            name: self.build_table(name)
            for name in SCHEMAS
        }

        result = self.validate_tables(
            tables, stats
        )

        self.target.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with tempfile.TemporaryDirectory(
            prefix=".parquet_stage_",
            dir=self.target.parent
        ) as temp_dir:

            stage = Path(temp_dir) / "business"
            stage.mkdir()

            files = {}

            for name, table in tables.items():

                filename = f"{name}.parquet"
                path = stage / filename

                pq.write_table(
                    table,
                    path,
                    compression="snappy"
                )

                reloaded = pq.ParquetFile(path).read()

                if not reloaded.equals(table):
                    raise ValueError(
                        f"Parquet round-trip failed: {name}"
                    )

                files[filename] = {
                    "rows": table.num_rows,
                    "sha256": self.fingerprint(path)
                }

            manifest = {
                "run_id": self.run_id,
                "format": "parquet",
                "compression": "snappy",
                "schema_version": "1.0",
                "source_hashes": source_hashes,
                "files": files,
                "statistics": result
            }

            with (
                stage / "_parquet_manifest.json"
            ).open(
                "w", encoding="utf-8"
            ) as file:

                json.dump(
                    manifest, file, indent=2
                )

            try:
                stage.rename(self.target)

            except PermissionError:

                if self.target.exists():
                    raise

                try:
                    shutil.copytree(stage, self.target)

                    for filename in files:

                        if (
                            self.fingerprint(stage / filename)
                            != self.fingerprint(
                                self.target / filename
                            )
                        ):
                            raise RuntimeError(
                                f"Copy verification failed: {filename}"
                            )

                except Exception:

                    if self.target.exists():
                        shutil.rmtree(self.target)

                    raise

        return "CREATED", result


if __name__ == "__main__":

    print("=" * 70)
    print("PHASE 8 - ANALYTICS PARQUET SUPPORT")
    print("=" * 70)

    writer = ParquetAnalyticsWriter()
    status, result = writer.run()

    print("\nStatus:", status)

    print("\nPARQUET RECONCILIATION:")

    for key, value in result.items():
        print(f"{key}: {value}")

    print("\nMoney column type:")
    print(SCHEMAS["daily_business_metrics"].field(
        "gross_revenue"
    ).type)

    print("\nOutput:")
    print(writer.target)

    print("\nANALYTICS PARQUET TEST PASSED.")
