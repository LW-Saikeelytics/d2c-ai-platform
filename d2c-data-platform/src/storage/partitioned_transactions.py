
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
INTEGER = pa.int64()
MONEY = pa.decimal128(18, 2)

SCHEMAS = {
    "orders": pa.schema([
        ("order_id", TEXT),
        ("customer_id", TEXT),
        ("segment", TEXT),
        ("city_id", TEXT),
        ("region", TEXT),
        ("channel", TEXT),
        ("product_id", TEXT),
        ("variant_id", TEXT),
        ("category", TEXT),
        ("subcategory", TEXT),
        ("quantity", INTEGER),
        ("unit_price", MONEY),
        ("gross_amount", MONEY)
    ]),
    "behavior_history": pa.schema([
        ("customer_id", TEXT),
        ("event_type", TEXT),
        ("product_id", TEXT),
        ("category", TEXT),
        ("event_id", TEXT)
    ])
}

PRIMARY_KEYS = {
    "orders": "order_id",
    "behavior_history": "event_id"
}

PARTITIONING = ds.partitioning(
    pa.schema([("simulation_day", INTEGER)]),
    flavor="hive"
)


class PartitionedTransactions:

    def __init__(self):

        self.ingestor = RawLayerIngestor()
        self.run_id = self.ingestor.run_id

        run_folder = f"run_id={self.run_id}"

        self.source_dir = (
            ROOT / "data" / "processed"
            / run_folder / "transactions"
        )

        self.output_root = (
            ROOT / "data" / "parquet"
            / run_folder / "processed"
        )

        manifest_path = (
            self.source_dir
            / "_processed_manifest.json"
        )

        with manifest_path.open(
            "r", encoding="utf-8"
        ) as file:
            manifest = json.load(file)

        if manifest["run_id"] != self.run_id:
            raise ValueError(
                "Processed transaction run mismatch"
            )

        self.expected_rows = {
            name: manifest["statistics"][name][
                "processed_rows"
            ]
            for name in SCHEMAS
        }

        entity_manifest = (
            ROOT / "data" / "processed"
            / run_folder / "entities"
            / "_processed_manifest.json"
        )

        with entity_manifest.open(
            "r", encoding="utf-8"
        ) as file:
            entity_stats = json.load(file)

        if entity_stats["run_id"] != self.run_id:
            raise ValueError("Entity run mismatch")

        self.expected_revenue = Decimal(
            entity_stats["statistics"][
                "reconciled_revenue"
            ]
        )

        activity_manifest = (
            ROOT / "data" / "processed"
            / run_folder / "activity"
            / "_processed_manifest.json"
        )

        with activity_manifest.open(
            "r", encoding="utf-8"
        ) as file:
            activity_stats = json.load(file)

        if activity_stats["run_id"] != self.run_id:
            raise ValueError("Activity run mismatch")

        self.max_day = activity_stats["statistics"][
            "clean_daily_metric_days"
        ]

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
    # READ AND VALIDATE SOURCE RECORDS
    # ==========================================

    def load_groups(self, name):

        schema = SCHEMAS[name]

        path = (
            self.source_dir / f"{name}.jsonl"
        )

        groups = defaultdict(list)
        seen_keys = set()
        total = 0

        expected_fields = (
            set(schema.names) | {"simulation_day"}
        )

        with path.open(
            "r", encoding="utf-8"
        ) as file:

            for line_number, line in enumerate(
                file, start=1
            ):

                if not line.strip():
                    continue

                row = json.loads(line)

                if set(row) != expected_fields:
                    raise ValueError(
                        f"Column mismatch: {name}, "
                        f"line {line_number}"
                    )

                day = row.pop("simulation_day")

                if (
                    type(day) is not int
                    or not 1 <= day <= self.max_day
                ):
                    raise ValueError(
                        f"Invalid simulation day: {day}"
                    )

                key = row[PRIMARY_KEYS[name]]

                if not isinstance(key, str) or not key:
                    raise ValueError(
                        f"Invalid primary key: {name}"
                    )

                if key in seen_keys:
                    raise ValueError(
                        f"Duplicate primary key: {key}"
                    )

                seen_keys.add(key)

                if name == "orders":

                    if (
                        type(row["quantity"]) is not int
                        or row["quantity"] <= 0
                    ):
                        raise ValueError(
                            f"Invalid quantity: {key}"
                        )

                    for column in (
                        "unit_price", "gross_amount"
                    ):

                        amount = Decimal(
                            str(row[column])
                        )

                        if (
                            not amount.is_finite()
                            or amount < 0
                            or amount != amount.quantize(
                                Decimal("0.01")
                            )
                        ):
                            raise ValueError(
                                f"Invalid {column}: {key}"
                            )

                        row[column] = amount

                groups[day].append(row)
                total += 1

        if total != self.expected_rows[name]:
            raise ValueError(
                f"{name} source count mismatch"
            )

        return groups

    # ==========================================
    # VERIFY PARTITION OUTPUT
    # ==========================================

    def verify(self, name, location, source_hash):

        manifest_path = (
            location / "_partition_manifest.json"
        )

        with manifest_path.open(
            "r", encoding="utf-8"
        ) as file:
            manifest = json.load(file)

        if (
            manifest["run_id"] != self.run_id
            or manifest["dataset"] != name
            or manifest["source_sha256"] != source_hash
        ):
            raise ValueError(
                f"{name}: manifest mismatch"
            )

        expected_files = (
            set(manifest["files"])
            | {"_partition_manifest.json"}
        )

        actual_files = {
            path.relative_to(location).as_posix()
            for path in location.rglob("*")
            if path.is_file()
        }

        if actual_files != expected_files:
            raise ValueError(
                f"{name}: partition inventory mismatch"
            )

        row_total = 0
        revenue = Decimal("0.00")

        for relative, metadata in manifest["files"].items():

            path = location / relative

            if (
                self.fingerprint(path)
                != metadata["sha256"]
            ):
                raise ValueError(
                    f"Checksum mismatch: {relative}"
                )

            table = pq.ParquetFile(path).read()

            if not table.schema.equals(SCHEMAS[name]):
                raise ValueError(
                    f"Schema mismatch: {relative}"
                )

            if table.num_rows != metadata["rows"]:
                raise ValueError(
                    f"Row mismatch: {relative}"
                )

            row_total += table.num_rows

            if name == "orders":

                revenue += sum(
                    table["gross_amount"].to_pylist(),
                    Decimal("0.00")
                )

        dataset = ds.dataset(
            location,
            format="parquet",
            partitioning=PARTITIONING
        )

        if set(dataset.schema.names) != (
            set(SCHEMAS[name].names)
            | {"simulation_day"}
        ):
            raise ValueError(
                f"{name}: dataset schema mismatch"
            )

        if not (
            row_total
            == dataset.count_rows()
            == self.expected_rows[name]
            == manifest["row_count"]
        ):
            raise ValueError(
                f"{name}: total rows do not reconcile"
            )

        if (
            name == "orders"
            and revenue != self.expected_revenue
        ):
            raise ValueError(
                "Partitioned order revenue mismatch"
            )

        result = {
            "partitions": len(manifest["files"]),
            "rows": row_total,
            "day_30_rows": dataset.count_rows(
                filter=(
                    ds.field("simulation_day") == 30
                )
            )
        }

        if name == "orders":
            result["gross_revenue"] = str(revenue)

        return result

    # ==========================================
    # CREATE OR VERIFY PARTITIONS
    # ==========================================

    def process(self, name):

        source_path = (
            self.source_dir / f"{name}.jsonl"
        )

        source_hash = self.fingerprint(source_path)

        target = self.output_root / name

        if target.exists():

            result = self.verify(
                name, target, source_hash
            )

            return "VERIFIED_EXISTING", result

        groups = self.load_groups(name)

        self.output_root.mkdir(
            parents=True, exist_ok=True
        )

        with tempfile.TemporaryDirectory(
            prefix=f".{name}_stage_",
            dir=self.output_root
        ) as temp_dir:

            stage = Path(temp_dir) / name
            stage.mkdir()

            files = {}

            for day in sorted(groups):

                directory = (
                    stage / f"simulation_day={day}"
                )

                directory.mkdir()

                table = pa.Table.from_pylist(
                    groups[day],
                    schema=SCHEMAS[name]
                )

                path = directory / "part.parquet"

                pq.write_table(
                    table,
                    path,
                    compression="snappy"
                )

                reloaded = pq.ParquetFile(path).read()

                if not reloaded.equals(table):
                    raise ValueError(
                        f"Round-trip mismatch: {name}, "
                        f"Day {day}"
                    )

                relative = (
                    path.relative_to(stage).as_posix()
                )

                files[relative] = {
                    "rows": table.num_rows,
                    "sha256": self.fingerprint(path)
                }

            manifest = {
                "run_id": self.run_id,
                "dataset": name,
                "schema_version": "1.0",
                "partition_column": "simulation_day",
                "source_sha256": source_hash,
                "row_count": self.expected_rows[name],
                "compression": "snappy",
                "files": files
            }

            with (
                stage / "_partition_manifest.json"
            ).open(
                "w", encoding="utf-8"
            ) as file:
                json.dump(manifest, file, indent=2)

            # Verify staged files before publishing.
            self.verify(name, stage, source_hash)

            try:
                stage.rename(target)

            except PermissionError:

                if target.exists():
                    raise

                try:
                    shutil.copytree(stage, target)

                    self.verify(
                        name, target, source_hash
                    )

                except Exception:

                    if target.exists():
                        shutil.rmtree(target)

                    raise

        result = self.verify(
            name, target, source_hash
        )

        return "CREATED", result

    def run(self):

        self.ingestor.ingest()

        results = {}

        for name in SCHEMAS:

            status, stats = self.process(name)

            results[name] = {
                "status": status,
                **stats
            }

        return results


if __name__ == "__main__":

    print("=" * 70)
    print("PHASE 8 - PARTITIONED TRANSACTIONS")
    print("=" * 70)

    writer = PartitionedTransactions()
    results = writer.run()

    for name, stats in results.items():

        print(f"\n{name.upper()}")
        print(f"Status: {stats['status']}")

        for key, value in stats.items():
            if key != "status":
                print(f"{key}: {value}")

    print("\nOutput root:")
    print(writer.output_root)

    print("\nPARTITIONED TRANSACTIONS TEST PASSED.")
