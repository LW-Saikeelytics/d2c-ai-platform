
import argparse
import getpass
import hashlib
import json

from decimal import Decimal
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

import pyarrow as pa
import pyarrow.dataset as ds

from src.storage.parquet_integrity_audit import run_audit
from src.storage.partitioned_events import EVENT_SCHEMA
from src.storage.partitioned_transactions import (
    SCHEMAS as TRANSACTION_SCHEMAS
)
from src.storage.remaining_processed_parquet import (
    SCHEMAS as CORE_SCHEMAS
)


ROOT = Path(__file__).resolve().parents[2]

DAY_PARTITIONING = ds.partitioning(
    pa.schema([("simulation_day", pa.int64())]),
    flavor="hive"
)

SOURCES = {
    "customers": "processed/core/customers.parquet",
    "product_master": "processed/core/product_master.parquet",
    "orders": "processed/orders",
    "events": "processed/events",
    "behavior_history": "processed/behavior_history",
    "conversion_history": "processed/core/conversion_history",
    "daily_metrics_source":
        "processed/core/daily_metrics_source.parquet",
    "daily_metrics_cleaned":
        "processed/core/daily_metrics_cleaned.parquet"
}

COLUMNS = {
    "customers": CORE_SCHEMAS["customers"].names,
    "product_master": CORE_SCHEMAS["product_master"].names,
    "orders": [
        "simulation_day",
        *TRANSACTION_SCHEMAS["orders"].names
    ],
    "events": [
        "simulation_day",
        *EVENT_SCHEMA.names
    ],
    "behavior_history": [
        "simulation_day",
        *TRANSACTION_SCHEMAS["behavior_history"].names
    ],
    "conversion_history": [
        "simulation_day",
        *CORE_SCHEMAS["conversion_history"].names
    ],
    "daily_metrics_source":
        CORE_SCHEMAS["daily_metrics_source"].names,
    "daily_metrics_cleaned":
        CORE_SCHEMAS["daily_metrics_cleaned"].names
}

PARTITIONED = {
    "orders",
    "events",
    "behavior_history",
    "conversion_history"
}

JSON_STRING_COLUMNS = {
    "result_json",
    "behavior_events_json",
    "conversion_json",
    "orders_json"
}


def read_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


class ParquetPostgresIngestor:

    def __init__(self, report):

        self.platform = read_json(
            ROOT / "config" / "platform_config.json"
        )

        self.database = read_json(
            ROOT / "config" / "database_config.json"
        )["database"]

        self.profile = read_json(
            ROOT / "reports" / "source_schema_profile.json"
        )

        self.run_id = self.platform["source"]["run_id"]

        if report["run_id"] != self.run_id:
            raise ValueError("Integrity report run mismatch")

        if report["status"] != "PASSED":
            raise ValueError("Integrity audit has not passed")

        self.report = report

        self.parquet_root = (
            ROOT / "data" / "parquet"
            / f"run_id={self.run_id}"
        )

        self.expected = {
            "customers":
                self.platform["expected_datasets"]["customers"],
            "product_master":
                self.profile["product_master"]["rows"],
            "orders": report["clean_orders"],
            "events": report["clean_events"],
            "behavior_history":
                report["clean_behavior_events"],
            "conversion_history":
                report["conversion_decisions"],
            "daily_metrics_source":
                report["daily_reconciliation_days"],
            "daily_metrics_cleaned":
                report["daily_reconciliation_days"]
        }

        self.expected_revenue = Decimal(
            report["gross_revenue_inr"]
        )

    # ==========================================
    # PARQUET SOURCE DISCOVERY
    # ==========================================

    def open_dataset(self, name):

        path = self.parquet_root / SOURCES[name]

        if not path.exists():
            raise FileNotFoundError(path)

        if name in PARTITIONED:
            dataset = ds.dataset(
                path,
                format="parquet",
                partitioning=DAY_PARTITIONING
            )
        else:
            dataset = ds.dataset(
                path,
                format="parquet"
            )

        if set(dataset.schema.names) != set(COLUMNS[name]):
            raise ValueError(
                f"Parquet columns do not match: {name}"
            )

        row_count = dataset.count_rows()

        if row_count != self.expected[name]:
            raise ValueError(
                f"{name}: expected {self.expected[name]} "
                f"rows, found {row_count}"
            )

        return dataset, path

    # ==========================================
    # DETERMINISTIC SOURCE FINGERPRINT
    # ==========================================

    def source_fingerprint(self, path):

        if path.is_file():
            files = [path]
        else:
            files = sorted(path.rglob("*.parquet"))

        if not files:
            raise ValueError(
                f"No Parquet files found: {path}"
            )

        digest = hashlib.sha256()

        for file_path in files:

            relative = file_path.relative_to(
                self.parquet_root
            ).as_posix()

            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")

            with file_path.open("rb") as file:

                for chunk in iter(
                    lambda: file.read(1024 * 1024),
                    b""
                ):
                    digest.update(chunk)

        return digest.hexdigest()

    # ==========================================
    # JSONB CONVERSION
    # ==========================================

    @staticmethod
    def convert_value(column, value):

        if column == "preferred_categories":
            return Jsonb(value)

        if column in JSON_STRING_COLUMNS:
            return Jsonb(json.loads(value))

        return value

    # ==========================================
    # VERIFY DATABASE CONTENT
    # ==========================================

    def verify_sql(self, cursor, name):

        table = sql.Identifier("staging", name)

        cursor.execute(
            sql.SQL(
                "SELECT COUNT(*) FROM {} WHERE run_id = %s"
            ).format(table),
            (self.run_id,)
        )

        actual = cursor.fetchone()[0]

        if actual != self.expected[name]:
            raise RuntimeError(
                f"{name}: PostgreSQL row count mismatch. "
                f"Expected {self.expected[name]}, found {actual}"
            )

        if name in ("customers", "orders"):

            money_column = (
                "lifetime_spend"
                if name == "customers"
                else "gross_amount"
            )

            cursor.execute(
                sql.SQL(
                    "SELECT COALESCE(SUM({}), 0) "
                    "FROM {} WHERE run_id = %s"
                ).format(
                    sql.Identifier(money_column),
                    table
                ),
                (self.run_id,)
            )

            revenue = cursor.fetchone()[0]

            if revenue != self.expected_revenue:
                raise RuntimeError(
                    f"{name}: PostgreSQL revenue mismatch. "
                    f"Found {revenue}"
                )

    # ==========================================
    # LOAD OR SAFELY REUSE ONE DATASET
    # ==========================================

    def ingest_dataset(self, connection, name):

        dataset, path = self.open_dataset(name)

        source_hash = self.source_fingerprint(path)
        expected_rows = self.expected[name]

        columns = COLUMNS[name]

        insert_query = sql.SQL(
            "INSERT INTO {} ({}) VALUES ({})"
        ).format(
            sql.Identifier("staging", name),
            sql.SQL(", ").join(
                sql.Identifier(column)
                for column in ["run_id", *columns]
            ),
            sql.SQL(", ").join(
                sql.Placeholder()
                for _ in range(len(columns) + 1)
            )
        )

        # One transaction per dataset.
        # Failed loads roll back both data and registry.
        with connection.transaction():

            with connection.cursor() as cursor:

                # Prevent simultaneous loads of the same
                # run/dataset from racing each other.
                cursor.execute(
                    "SELECT pg_advisory_xact_lock("
                    "hashtext(%s), hashtext(%s))",
                    (self.run_id, name)
                )

                cursor.execute(
                    """
                    SELECT
                        source_sha256,
                        expected_rows,
                        loaded_rows
                    FROM staging.ingestion_registry
                    WHERE run_id = %s
                      AND dataset_name = %s
                    """,
                    (self.run_id, name)
                )

                registry = cursor.fetchone()

                if registry is not None:

                    if registry != (
                        source_hash,
                        expected_rows,
                        expected_rows
                    ):
                        raise RuntimeError(
                            f"{name}: existing ingestion "
                            "registry does not match source"
                        )

                    self.verify_sql(cursor, name)

                    return "VERIFIED_EXISTING"

                # Do not load into an unexplained,
                # nonempty table.
                cursor.execute(
                    sql.SQL(
                        "SELECT COUNT(*) FROM {} "
                        "WHERE run_id = %s"
                    ).format(
                        sql.Identifier("staging", name)
                    ),
                    (self.run_id,)
                )

                if cursor.fetchone()[0] != 0:
                    raise RuntimeError(
                        f"{name}: rows exist without "
                        "an ingestion registry entry"
                    )

                inserted = 0

                for batch in dataset.to_batches(
                    columns=columns,
                    batch_size=1000
                ):

                    parameters = []

                    for row in batch.to_pylist():

                        values = tuple(
                            self.convert_value(
                                column,
                                row[column]
                            )
                            for column in columns
                        )

                        parameters.append(
                            (self.run_id, *values)
                        )

                    if parameters:
                        cursor.executemany(
                            insert_query,
                            parameters
                        )

                        inserted += len(parameters)

                if inserted != expected_rows:
                    raise RuntimeError(
                        f"{name}: inserted {inserted} "
                        f"of {expected_rows} expected rows"
                    )

                self.verify_sql(cursor, name)

                cursor.execute(
                    """
                    INSERT INTO staging.ingestion_registry (
                        run_id,
                        dataset_name,
                        source_sha256,
                        expected_rows,
                        loaded_rows
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        self.run_id,
                        name,
                        source_hash,
                        expected_rows,
                        inserted
                    )
                )

        return "LOADED"

    # ==========================================
    # RUN SELECTED DATASETS
    # ==========================================

    def run(self, names):

        password = getpass.getpass(
            "Enter dreamnest_app password: "
        )

        with psycopg.connect(
            host=self.database["host"],
            port=self.database["port"],
            dbname=self.database["name"],
            user=self.database["user"],
            password=password,
            connect_timeout=10,
            autocommit=True
        ) as connection:

            with connection.cursor() as cursor:

                cursor.execute(
                    "SELECT current_database(), current_user"
                )

                actual_database, actual_user = (
                    cursor.fetchone()
                )

                if (
                    actual_database != self.database["name"]
                    or actual_user != self.database["user"]
                ):
                    raise RuntimeError(
                        "Unexpected database or connected user"
                    )

            for name in names:

                print(f"\nDATASET: {name}", flush=True)

                status = self.ingest_dataset(
                    connection, name
                )

                print(f"Status: {status}")
                print(f"Rows: {self.expected[name]:,}")

        print("\nPOSTGRESQL INGESTION TEST PASSED.")


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--datasets",
        nargs="+",
        choices=list(SOURCES),
        default=list(SOURCES),
        help="Datasets to ingest; default is all eight"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("PHASE 8 - PARQUET TO POSTGRESQL INGESTION")
    print("=" * 70)

    # Validate every Parquet dataset before SQL writes.
    report, _ = run_audit()

    ingestor = ParquetPostgresIngestor(report)

    ingestor.run(args.datasets)
