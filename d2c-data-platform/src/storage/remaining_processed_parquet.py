
import hashlib
import json
import shutil
import tempfile

from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from src.layers.raw_layer import RawLayerIngestor


ROOT = Path(__file__).resolve().parents[2]

TEXT = pa.string()
INT = pa.int64()
MONEY = pa.decimal128(18, 2)


# ==========================================
# EXPLICIT PARQUET SCHEMAS
# ==========================================

SCHEMAS = {
    "customers": pa.schema([
        ("customer_id", TEXT),
        ("segment", TEXT),
        ("price_tendency", TEXT),
        ("discount_sensitivity", TEXT),
        ("premium_product_tendency", TEXT),
        ("repeat_purchase_tendency", TEXT),
        ("city_id", TEXT),
        ("region", TEXT),
        ("acquisition_channel", TEXT),
        ("registration_day", INT),
        ("lifetime_orders", INT),
        ("lifetime_spend", MONEY),
        ("last_order_day", INT),
        ("preferred_categories", pa.list_(TEXT)),
        ("purchase_propensity", pa.float64()),
        ("behavior_profile", TEXT),
        ("status", TEXT),
    ]),

    "product_master": pa.schema([
        ("product_id", TEXT),
        ("product_name", TEXT),
        ("category", TEXT),
        ("subcategory", TEXT),
        ("product_type", TEXT),
        ("price_band", TEXT),
        ("positioning", TEXT),
        ("launch_day", INT),
        ("discontinue_day", INT),
    ]),

    "conversion_history": pa.schema([
        ("customer_id", TEXT),
        ("result_json", TEXT),
    ]),

    "daily_metrics_source": pa.schema([
        ("simulation_day", INT),
        ("customers", INT),
        ("behavior_events_json", TEXT),
        ("conversion_json", TEXT),
        ("orders_json", TEXT),
        ("purchase_events", INT),
    ]),

    "daily_metrics_cleaned": pa.schema([
        ("simulation_day", INT),
        ("customers", INT),
        ("behavior_event_count", INT),
        ("behavior_active_customers", INT),
        ("conversion_decisions_evaluated", INT),
        ("historical_converted_decisions", INT),
        ("clean_order_count", INT),
        ("clean_purchase_event_count", INT),
        ("clean_event_count", INT),
    ]),
}


SECTIONS = {
    "customers": "entities",
    "product_master": "entities",
    "conversion_history": "activity",
    "daily_metrics_source": "activity",
    "daily_metrics_cleaned": "activity",
}


PRIMARY_KEYS = {
    "customers": ("customer_id",),
    "product_master": ("product_id",),
    "conversion_history": (
        "simulation_day",
        "customer_id"
    ),
    "daily_metrics_source": ("simulation_day",),
    "daily_metrics_cleaned": ("simulation_day",),
}


class RemainingProcessedParquet:

    def __init__(self):

        self.ingestor = RawLayerIngestor()
        self.run_id = self.ingestor.run_id

        folder = f"run_id={self.run_id}"

        self.source = (
            ROOT / "data" / "processed" / folder
        )

        self.target = (
            ROOT / "data" / "parquet"
            / folder / "processed" / "core"
        )

        self.entity_stats = self.load_manifest(
            "entities"
        )["statistics"]

        self.activity_stats = self.load_manifest(
            "activity"
        )["statistics"]

        self.expected = {
            "customers":
                self.entity_stats["customer_rows"],

            "product_master":
                self.entity_stats["product_rows"],

            "conversion_history":
                self.activity_stats[
                    "conversion_history_rows"
                ],

            "daily_metrics_source":
                self.activity_stats[
                    "original_daily_metric_days"
                ],

            "daily_metrics_cleaned":
                self.activity_stats[
                    "clean_daily_metric_days"
                ],
        }

    # ==========================================
    # SOURCE HELPERS
    # ==========================================

    def load_manifest(self, section):

        path = (
            self.source / section
            / "_processed_manifest.json"
        )

        with path.open(
            "r", encoding="utf-8"
        ) as file:
            manifest = json.load(file)

        if manifest["run_id"] != self.run_id:
            raise ValueError(
                f"Run ID mismatch: {section}"
            )

        return manifest

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

    def source_path(self, name):

        return (
            self.source
            / SECTIONS[name]
            / f"{name}.jsonl"
        )

    # ==========================================
    # LOAD AND STANDARDIZE
    # ==========================================

    def load_table(self, name):

        records = []
        seen_keys = set()

        with self.source_path(name).open(
            "r", encoding="utf-8"
        ) as file:

            for number, line in enumerate(
                file, start=1
            ):

                if not line.strip():
                    continue

                row = json.loads(line)

                key = tuple(
                    row[column]
                    for column in PRIMARY_KEYS[name]
                )

                if key in seen_keys:
                    raise ValueError(
                        f"Duplicate key: {name}, "
                        f"line {number}"
                    )

                seen_keys.add(key)

                if name == "customers":

                    money = Decimal(
                        str(row["lifetime_spend"])
                    )

                    if (
                        not money.is_finite()
                        or money < 0
                        or money != money.quantize(
                            Decimal("0.01")
                        )
                    ):
                        raise ValueError(
                            "Invalid customer lifetime spend"
                        )

                    row["lifetime_spend"] = money

                    categories = row[
                        "preferred_categories"
                    ]

                    if (
                        not isinstance(categories, list)
                        or not all(
                            isinstance(item, str)
                            for item in categories
                        )
                    ):
                        raise ValueError(
                            "Invalid preferred categories"
                        )

                elif name == "conversion_history":

                    result = row["result"]

                    if (
                        not isinstance(result, dict)
                        or type(
                            result.get("converted")
                        ) is not bool
                    ):
                        raise ValueError(
                            "Invalid conversion decision"
                        )

                    row["result_json"] = json.dumps(
                        row.pop("result"),
                        sort_keys=True
                    )

                elif name == "daily_metrics_source":

                    for column in (
                        "behavior_events",
                        "conversion",
                        "orders"
                    ):

                        row[
                            column + "_json"
                        ] = json.dumps(
                            row.pop(column),
                            sort_keys=True
                        )

                expected_fields = set(
                    SCHEMAS[name].names
                )

                if name == "conversion_history":
                    expected_fields.add(
                        "simulation_day"
                    )

                if set(row) != expected_fields:
                    raise ValueError(
                        f"Schema mismatch: {name}, "
                        f"line {number}"
                    )

                records.append(row)

        if len(records) != self.expected[name]:
            raise ValueError(
                f"Row count mismatch: {name}"
            )

        return records

    # ==========================================
    # CROSS-DATASET RECONCILIATION
    # ==========================================

    def reconcile(self, tables):

        customers = tables["customers"]
        conversions = tables[
            "conversion_history"
        ]
        daily = tables[
            "daily_metrics_cleaned"
        ]

        historical_converted = sum(
            json.loads(
                row["result_json"]
            )["converted"]
            for row in conversions
        )

        daily_historical = sum(
            row["historical_converted_decisions"]
            for row in daily
        )

        if historical_converted != daily_historical:
            raise ValueError(
                "Historical conversion mismatch"
            )

        if sum(
            row["lifetime_orders"]
            for row in customers
        ) != self.activity_stats["clean_orders"]:
            raise ValueError(
                "Customer order totals mismatch"
            )

        total_spend = sum(
            (
                row["lifetime_spend"]
                for row in customers
            ),
            Decimal("0.00")
        )

        expected_revenue = Decimal(
            self.entity_stats["reconciled_revenue"]
        )

        if total_spend != expected_revenue:
            raise ValueError(
                "Customer revenue mismatch"
            )

        checks = {
            "clean_order_count":
                self.activity_stats["clean_orders"],

            "behavior_event_count":
                self.activity_stats[
                    "clean_behavior_events"
                ],

            "clean_event_count":
                self.activity_stats["clean_events"],

            "conversion_decisions_evaluated":
                self.activity_stats[
                    "conversion_history_rows"
                ],
        }

        for column, expected in checks.items():

            actual = sum(
                row[column] for row in daily
            )

            if actual != expected:
                raise ValueError(
                    f"Daily total mismatch: {column}"
                )

        days = list(
            range(
                1,
                self.expected[
                    "daily_metrics_cleaned"
                ] + 1
            )
        )

        for name in (
            "daily_metrics_source",
            "daily_metrics_cleaned"
        ):

            actual_days = sorted(
                row["simulation_day"]
                for row in tables[name]
            )

            if actual_days != days:
                raise ValueError(
                    f"Daily coverage mismatch: {name}"
                )

        if any(
            row["simulation_day"] not in days
            for row in conversions
        ):
            raise ValueError(
                "Conversion outside simulation window"
            )

        return {
            "customer_revenue": str(total_spend),
            "historical_conversions":
                historical_converted
        }

    # ==========================================
    # VERIFY PARQUET OUTPUT
    # ==========================================

    def verify(self, location, source_hashes):

        manifest_path = (
            location / "_parquet_manifest.json"
        )

        with manifest_path.open(
            "r", encoding="utf-8"
        ) as file:
            manifest = json.load(file)

        if (
            manifest["run_id"] != self.run_id
            or manifest["source_hashes"]
            != source_hashes
        ):
            raise ValueError(
                "Parquet manifest mismatch"
            )

        expected_files = (
            set(manifest["files"])
            | {"_parquet_manifest.json"}
        )

        actual_files = {
            path.relative_to(
                location
            ).as_posix()
            for path in location.rglob("*")
            if path.is_file()
        }

        if actual_files != expected_files:
            raise ValueError(
                "Parquet file inventory mismatch"
            )

        totals = defaultdict(int)

        for relative, metadata in (
            manifest["files"].items()
        ):

            path = location / relative

            if (
                self.fingerprint(path)
                != metadata["sha256"]
            ):
                raise ValueError(
                    f"Checksum mismatch: {relative}"
                )

            table = pq.ParquetFile(path).read()

            if "/" in relative:
                name = relative.split("/")[0]
            else:
                name = relative.removesuffix(
                    ".parquet"
                )

            if not table.schema.equals(
                SCHEMAS[name]
            ):
                raise ValueError(
                    f"Schema mismatch: {relative}"
                )

            if table.num_rows != metadata["rows"]:
                raise ValueError(
                    f"Row mismatch: {relative}"
                )

            totals[name] += table.num_rows

        for name in SCHEMAS:

            if totals[name] != self.expected[name]:
                raise ValueError(
                    f"Parquet count mismatch: {name}"
                )

        partitioning = ds.partitioning(
            pa.schema([
                ("simulation_day", INT)
            ]),
            flavor="hive"
        )

        conversion_dataset = ds.dataset(
            location / "conversion_history",
            format="parquet",
            partitioning=partitioning
        )

        if conversion_dataset.count_rows() != (
            self.expected["conversion_history"]
        ):
            raise ValueError(
                "Conversion partition count mismatch"
            )

        conversion_partitions = sum(
            path.startswith(
                "conversion_history/"
            )
            for path in manifest["files"]
        )

        return {
            "customers": totals["customers"],
            "products": totals["product_master"],
            "conversion_decisions":
                totals["conversion_history"],
            "conversion_day_partitions":
                conversion_partitions,
            "daily_metrics_source":
                totals["daily_metrics_source"],
            "daily_metrics_cleaned":
                totals["daily_metrics_cleaned"],
            "day_30_conversions":
                conversion_dataset.count_rows(
                    filter=(
                        ds.field("simulation_day") == 30
                    )
                ),
            **manifest["reconciliation"]
        }

    # ==========================================
    # BUILD PARQUET OUTPUT
    # ==========================================

    def run(self):

        self.ingestor.ingest()

        source_hashes = {
            name: self.fingerprint(
                self.source_path(name)
            )
            for name in SCHEMAS
        }

        if self.target.exists():

            result = self.verify(
                self.target, source_hashes
            )

            return "VERIFIED_EXISTING", result

        tables = {
            name: self.load_table(name)
            for name in SCHEMAS
        }

        reconciliation = self.reconcile(
            tables
        )

        self.target.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with tempfile.TemporaryDirectory(
            prefix=".core_stage_",
            dir=self.target.parent
        ) as temp_dir:

            stage = Path(temp_dir) / "core"
            stage.mkdir()

            files = {}

            def write_table(
                relative, records, schema
            ):

                path = stage / relative

                path.parent.mkdir(
                    parents=True,
                    exist_ok=True
                )

                table = pa.Table.from_pylist(
                    records,
                    schema=schema
                )

                pq.write_table(
                    table,
                    path,
                    compression="snappy"
                )

                reloaded = pq.ParquetFile(
                    path
                ).read()

                if not reloaded.equals(table):
                    raise ValueError(
                        f"Parquet round-trip failed: "
                        f"{relative}"
                    )

                files[relative] = {
                    "rows": table.num_rows,
                    "sha256": self.fingerprint(
                        path
                    )
                }

            for name, records in tables.items():

                if name == "conversion_history":

                    groups = defaultdict(list)

                    for record in records:

                        day = record[
                            "simulation_day"
                        ]

                        groups[day].append({
                            "customer_id":
                                record["customer_id"],

                            "result_json":
                                record["result_json"]
                        })

                    for day in sorted(groups):

                        write_table(
                            "conversion_history/"
                            f"simulation_day={day}/"
                            "part.parquet",
                            groups[day],
                            SCHEMAS[name]
                        )

                else:

                    write_table(
                        f"{name}.parquet",
                        records,
                        SCHEMAS[name]
                    )

            manifest = {
                "run_id": self.run_id,
                "schema_version": "1.0",
                "compression": "snappy",
                "source_hashes": source_hashes,
                "files": files,
                "reconciliation": reconciliation
            }

            with (
                stage / "_parquet_manifest.json"
            ).open(
                "w", encoding="utf-8"
            ) as file:

                json.dump(
                    manifest,
                    file,
                    indent=2
                )

            # Validate before publishing.
            self.verify(
                stage, source_hashes
            )

            try:
                stage.rename(self.target)

            except PermissionError:

                if self.target.exists():
                    raise

                try:

                    shutil.copytree(
                        stage,
                        self.target
                    )

                    self.verify(
                        self.target,
                        source_hashes
                    )

                except Exception:

                    if self.target.exists():
                        shutil.rmtree(
                            self.target
                        )

                    raise

        result = self.verify(
            self.target, source_hashes
        )

        return "CREATED", result


if __name__ == "__main__":

    print("=" * 70)
    print(
        "PHASE 8 - REMAINING PROCESSED PARQUET"
    )
    print("=" * 70)

    writer = RemainingProcessedParquet()

    status, result = writer.run()

    print("\nStatus:", status)

    print("\nPARQUET VALIDATION:")

    for key, value in result.items():
        print(f"{key}: {value}")

    print("\nOutput:")
    print(writer.target)

    print(
        "\nREMAINING PROCESSED PARQUET TEST PASSED."
    )
