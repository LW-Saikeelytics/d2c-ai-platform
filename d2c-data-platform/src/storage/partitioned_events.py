
import hashlib
import json
import shutil
import tempfile

from collections import defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from src.layers.raw_layer import RawLayerIngestor


ROOT = Path(__file__).resolve().parents[2]

EVENT_SCHEMA = pa.schema([
    ("customer_id", pa.string()),
    ("event_type", pa.string()),
    ("product_id", pa.string()),
    ("category", pa.string()),
    ("event_id", pa.string()),
    ("order_id", pa.string())
])

PARTITION_SCHEMA = pa.schema([
    ("simulation_day", pa.int64())
])


class PartitionedEvents:

    def __init__(self):

        self.ingestor = RawLayerIngestor()
        self.run_id = self.ingestor.run_id

        run_folder = f"run_id={self.run_id}"

        self.processed = (
            ROOT / "data" / "processed"
            / run_folder / "transactions"
        )

        self.source = (
            self.processed / "events.jsonl"
        )

        self.target = (
            ROOT / "data" / "parquet"
            / run_folder / "processed" / "events"
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

    def expected_counts(self):

        path = (
            self.processed
            / "_processed_manifest.json"
        )

        with path.open("r", encoding="utf-8") as file:
            manifest = json.load(file)

        if manifest["run_id"] != self.run_id:
            raise ValueError("Processed run ID mismatch")

        stats = manifest["statistics"]

        return {
            "events": stats["events"]["processed_rows"],
            "purchases": stats["orders"]["processed_rows"]
        }

    def read_events(self):

        groups = defaultdict(list)
        event_ids = set()
        purchases = 0
        total = 0

        expected_fields = (
            set(EVENT_SCHEMA.names)
            | {"simulation_day"}
        )

        with self.source.open(
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
                        f"Unexpected event fields: "
                        f"line {line_number}"
                    )

                day = row.pop("simulation_day")

                if (
                    type(day) is not int
                    or not 1 <= day <= 90
                ):
                    raise ValueError(
                        f"Invalid day: {day}"
                    )

                event_id = row["event_id"]

                if event_id in event_ids:
                    raise ValueError(
                        f"Duplicate event: {event_id}"
                    )

                event_ids.add(event_id)

                if row["event_type"] == "purchase":

                    if not row["order_id"]:
                        raise ValueError(
                            "Purchase event missing order ID"
                        )

                    purchases += 1

                elif row["order_id"] is not None:

                    raise ValueError(
                        "Non-purchase event has order ID"
                    )

                groups[day].append(row)
                total += 1

        expected = self.expected_counts()

        if (
            total != expected["events"]
            or purchases != expected["purchases"]
        ):
            raise ValueError(
                "Source event counts do not reconcile"
            )

        return groups, total, purchases

    def verify_output(self, location, manifest):

        expected_files = (
            set(manifest["partitions"])
            | {"_partition_manifest.json"}
        )

        actual_files = {
            path.relative_to(location).as_posix()
            for path in location.rglob("*")
            if path.is_file()
        }

        if actual_files != expected_files:
            raise ValueError(
                "Partition inventory mismatch"
            )

        for relative, metadata in (
            manifest["partitions"].items()
        ):

            path = location / relative

            if (
                self.fingerprint(path)
                != metadata["sha256"]
            ):
                raise ValueError(
                    f"Partition checksum mismatch: {relative}"
                )

        partitioning = ds.partitioning(
            PARTITION_SCHEMA,
            flavor="hive"
        )

        dataset = ds.dataset(
            location,
            format="parquet",
            partitioning=partitioning
        )

        expected_columns = (
            set(EVENT_SCHEMA.names)
            | {"simulation_day"}
        )

        if set(dataset.schema.names) != expected_columns:
            raise ValueError(
                "Partitioned dataset schema mismatch"
            )

        total = dataset.count_rows()

        purchases = dataset.count_rows(
            filter=(
                ds.field("event_type") == "purchase"
            )
        )

        day_30 = dataset.count_rows(
            filter=(
                ds.field("simulation_day") == 30
            )
        )

        if total != manifest["event_count"]:
            raise ValueError(
                "Partition event count mismatch"
            )

        if purchases != manifest["purchase_count"]:
            raise ValueError(
                "Partition purchase count mismatch"
            )

        if sum(
            item["rows"]
            for item in manifest["partitions"].values()
        ) != total:
            raise ValueError(
                "Partition row totals mismatch"
            )

        return {
            "partitions": len(manifest["partitions"]),
            "events": total,
            "purchases": purchases,
            "day_30_events": day_30
        }

    def run(self):

        # Verify original raw snapshot.
        self.ingestor.ingest()

        source_hash = self.fingerprint(self.source)

        if self.target.exists():

            manifest_path = (
                self.target
                / "_partition_manifest.json"
            )

            with manifest_path.open(
                "r", encoding="utf-8"
            ) as file:
                manifest = json.load(file)

            if (
                manifest["run_id"] != self.run_id
                or manifest["source_sha256"]
                != source_hash
            ):
                raise ValueError(
                    "Existing partition source mismatch"
                )

            result = self.verify_output(
                self.target, manifest
            )

            return "VERIFIED_EXISTING", result

        groups, total, purchases = self.read_events()

        self.target.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with tempfile.TemporaryDirectory(
            prefix=".events_stage_",
            dir=self.target.parent
        ) as temp_dir:

            stage = Path(temp_dir) / "events"
            stage.mkdir()

            partition_files = {}

            for day in sorted(groups):

                directory = (
                    stage
                    / f"simulation_day={day}"
                )

                directory.mkdir()

                table = pa.Table.from_pylist(
                    groups[day],
                    schema=EVENT_SCHEMA
                )

                path = directory / "events.parquet"

                pq.write_table(
                    table,
                    path,
                    compression="snappy"
                )

                reloaded = pq.read_table(path)

                if not reloaded.equals(table):
                    raise ValueError(
                        f"Parquet round-trip failed: Day {day}"
                    )

                relative = (
                    path.relative_to(stage).as_posix()
                )

                partition_files[relative] = {
                    "rows": table.num_rows,
                    "sha256": self.fingerprint(path)
                }

            manifest = {
                "run_id": self.run_id,
                "schema_version": "1.0",
                "partition_column": "simulation_day",
                "compression": "snappy",
                "source_sha256": source_hash,
                "event_count": total,
                "purchase_count": purchases,
                "partitions": partition_files
            }

            with (
                stage / "_partition_manifest.json"
            ).open("w", encoding="utf-8") as file:

                json.dump(
                    manifest, file, indent=2
                )

            # Validate the staged dataset first.
            result = self.verify_output(
                stage, manifest
            )

            try:
                stage.rename(self.target)

            except PermissionError:

                if self.target.exists():
                    raise

                try:
                    shutil.copytree(stage, self.target)

                    # Verify all copied files.
                    for original in stage.rglob("*"):

                        if not original.is_file():
                            continue

                        relative = original.relative_to(stage)
                        copied = self.target / relative

                        if (
                            self.fingerprint(original)
                            != self.fingerprint(copied)
                        ):
                            raise RuntimeError(
                                f"Copy failed: {relative}"
                            )

                except Exception:

                    if self.target.exists():
                        shutil.rmtree(self.target)

                    raise

        return "CREATED", result


if __name__ == "__main__":

    print("=" * 70)
    print("PHASE 8 - PARTITIONED EVENTS PARQUET")
    print("=" * 70)

    writer = PartitionedEvents()
    status, result = writer.run()

    print("\nStatus:", status)

    print("\nPARTITION VALIDATION:")

    for key, value in result.items():
        print(f"{key}: {value:,}")

    print("\nOutput:")
    print(writer.target)

    print("\nPARTITIONED EVENTS TEST PASSED.")
