from pathlib import Path
from datetime import datetime
import csv
import json

class DatasetWriter:
    """
    Handles creation of simulation export directories
    and writing simulation datasets.
    """

    def __init__(self, base_output_dir="data/generated"):
        self.base_output_dir = Path(base_output_dir)

        # Create base output directory if it does not exist
        self.base_output_dir.mkdir(parents=True, exist_ok=True)

        self.run_id = None
        self.run_directory = None

    def create_run_directory(self, run_id=None):
        """
        Creates a unique directory for a simulation run.
        """

        if run_id is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            run_id = f"simulation_run_{timestamp}"

        self.run_id = run_id
        self.run_directory = self.base_output_dir / run_id

        self.run_directory.mkdir(parents=True, exist_ok=True)

        return self.run_directory

    def _mapping_to_records(self, mapping, id_field):
        """
        Converts a dictionary of records into a list of dictionaries.

        Example:

        {
            "ORD001": {"amount": 50},
            "ORD002": {"amount": 75}
        }

        becomes:

        [
            {"order_id": "ORD001", "amount": 50},
            {"order_id": "ORD002", "amount": 75}
        ]
        """

        records = []

        for record_id, record_data in mapping.items():

            if isinstance(record_data, dict):
                record = dict(record_data)
            else:
                record = {
                    "value": record_data
                }

            # Preserve the dictionary key as an ID
            # unless the record already contains that ID.
            record.setdefault(
                id_field,
                record_id
            )

            records.append(record)

        return records

    def _serialize_csv_value(self, value):
        """
        Converts complex Python values into CSV-safe values.
        """

        if isinstance(value, (dict, list, tuple)):
            return json.dumps(
                value,
                ensure_ascii=False,
                default=str
            )

        return value

    def write_csv(self, filename, records):
        """
        Writes a list of dictionaries to a CSV file.
        """

        if self.run_directory is None:
            raise RuntimeError(
                "Run directory has not been created. "
                "Call create_run_directory() first."
            )

        if not records:
            print(f"No records available for {filename}. CSV not created.")
            return None

        file_path = self.run_directory / filename

        # Collect all possible field names
        fieldnames = []

        for record in records:
            for key in record.keys():
                if key not in fieldnames:
                    fieldnames.append(key)

        with file_path.open(
            mode="w",
            newline="",
            encoding="utf-8"
        ) as csv_file:

            writer = csv.DictWriter(
                csv_file,
                fieldnames=fieldnames,
                extrasaction="ignore"
            )

            writer.writeheader()
            prepared_records = []
            for record in records:

                prepared_record = {
                    key: self._serialize_csv_value(value)
                    for key, value in record.items()
                }

                prepared_records.append(
                    prepared_record
                )

            writer.writerows(
                prepared_records
            )

        return file_path

    def write_jsonl(self, filename, records):
        """
        Writes a list of dictionaries to a JSONL file.
        Each record is stored as one JSON object per line.
        """

        if self.run_directory is None:
            raise RuntimeError(
                "Run directory has not been created. "
                "Call create_run_directory() first."
            )

        if not records:
            print(f"No records available for {filename}. JSONL not created.")
            return None

        file_path = self.run_directory / filename

        with file_path.open(
            mode="w",
            encoding="utf-8"
        ) as jsonl_file:

            for record in records:
                json_line = json.dumps(
                    record,
                    ensure_ascii=False,
                    default=str
                )

                jsonl_file.write(json_line + "\n")

        return file_path

    def write_manifest(self, metadata):
        """
        Writes simulation run metadata to a manifest JSON file.
        """

        if self.run_directory is None:
            raise RuntimeError(
                "Run directory has not been created. "
                "Call create_run_directory() first."
            )

        manifest_path = self.run_directory / "simulation_manifest.json"

        manifest = {
            "run_id": self.run_id,
            "created_at": datetime.now().isoformat(),
            **metadata
        }

        with manifest_path.open(
            mode="w",
            encoding="utf-8"
        ) as manifest_file:

            json.dump(
                manifest,
                manifest_file,
                indent=4,
                ensure_ascii=False,
                default=str
            )

        return manifest_path

    def export_datasets(self, datasets, metadata=None):
        """
        Exports multiple simulation datasets as CSV and JSONL
        and creates a manifest describing the exported run.

        datasets format:

        {
            "customers": [...],
            "orders": [...],
            "events": [...],
            "daily_metrics": [...]
        }
        """

        if self.run_directory is None:
            raise RuntimeError(
                "Run directory has not been created. "
                "Call create_run_directory() first."
            )

        exported_files = []
        dataset_summary = {}

        for dataset_name, records in datasets.items():

            if not records:
                dataset_summary[dataset_name] = {
                    "record_count": 0,
                    "files": []
                }
                continue

            csv_filename = f"{dataset_name}.csv"
            jsonl_filename = f"{dataset_name}.jsonl"

            csv_path = self.write_csv(
                filename=csv_filename,
                records=records
            )

            jsonl_path = self.write_jsonl(
                filename=jsonl_filename,
                records=records
            )

            dataset_files = []

            if csv_path:
                exported_files.append(csv_filename)
                dataset_files.append(csv_filename)

            if jsonl_path:
                exported_files.append(jsonl_filename)
                dataset_files.append(jsonl_filename)

            dataset_summary[dataset_name] = {
                "record_count": len(records),
                "files": dataset_files
            }

        manifest_metadata = {
            "datasets": dataset_summary,
            "exported_files": exported_files
        }

        if metadata:
            manifest_metadata.update(metadata)

        manifest_path = self.write_manifest(
            metadata=manifest_metadata
        )

        return {
            "run_id": self.run_id,
            "run_directory": self.run_directory,
            "datasets": dataset_summary,
            "manifest": manifest_path
        }

    def export_simulation_state(self, state):
        """
        Exports persistent datasets from a SimulationState instance.
        """

        if self.run_directory is None:
            raise RuntimeError(
                "Run directory has not been created. "
                "Call create_run_directory() first."
            )

        # --------------------------------------------------
        # NORMALIZE SIMULATION STATE
        # --------------------------------------------------

        customers = self._mapping_to_records(
            state.customers,
            "customer_id"
        )

        orders = self._mapping_to_records(
            state.orders,
            "order_id"
        )

        events = self._mapping_to_records(
            state.events,
            "event_id"
        )

        daily_metrics = list(
            state.daily_metrics
        )

        behavior_history = list(
            state.behavior_history
        )

        conversion_history = list(
            state.conversion_history
        )

        # --------------------------------------------------
        # DATASETS
        # --------------------------------------------------

        datasets = {
            "customers": customers,
            "orders": orders,
            "events": events,
            "daily_metrics": daily_metrics,
            "behavior_history": behavior_history,
            "conversion_history": conversion_history
        }

        # --------------------------------------------------
        # RUN METADATA
        # --------------------------------------------------

        metadata = {
            "simulation_current_day": state.current_day,

            "simulation_current_date": (
                state.current_date.isoformat()
                if state.current_date is not None
                else None
            ),

            "customer_count": len(
                state.customers
            ),

            "order_count": len(
                state.orders
            ),

            "event_count": len(
                state.events
            ),

            "daily_metrics_count": len(
                state.daily_metrics
            ),

            "behavior_history_count": len(
                state.behavior_history
            ),

            "conversion_history_count": len(
                state.conversion_history
            ),

            "counters": dict(
                state.counters
            )
        }

        # --------------------------------------------------
        # EXPORT
        # --------------------------------------------------

        return self.export_datasets(
            datasets=datasets,
            metadata=metadata
        )

if __name__ == "__main__":

    writer = DatasetWriter()

    run_directory = writer.create_run_directory()

    print("=" * 60)
    print("DATASET WRITER TEST")
    print("=" * 60)

    print(f"Run ID: {writer.run_id}")
    print(f"Output directory: {run_directory}")

    test_customers = [
        {
            "customer_id": "CUST001",
            "segment": "high_value"
        },
        {
            "customer_id": "CUST002",
            "segment": "regular"
        }
    ]

    test_orders = [
        {
            "order_id": "ORD001",
            "customer_id": "CUST001",
            "day": 1,
            "total_amount": 89.99
        },
        {
            "order_id": "ORD002",
            "customer_id": "CUST002",
            "day": 3,
            "total_amount": 45.50
        },
        {
            "order_id": "ORD003",
            "customer_id": "CUST001",
            "day": 7,
            "total_amount": 120.00
        }
    ]

    test_events = [
        {
            "event_id": "EVT001",
            "customer_id": "CUST001",
            "day": 1,
            "event_type": "product_view"
        },
        {
            "event_id": "EVT002",
            "customer_id": "CUST002",
            "day": 2,
            "event_type": "add_to_cart"
        },
        {
            "event_id": "EVT003",
            "customer_id": "CUST001",
            "day": 7,
            "event_type": "purchase"
        }
    ]

    test_daily_metrics = [
        {
            "day": 1,
            "orders": 1,
            "events": 1
        },
        {
            "day": 2,
            "orders": 0,
            "events": 1
        },
        {
            "day": 3,
            "orders": 1,
            "events": 0
        },
        {
            "day": 7,
            "orders": 1,
            "events": 1
        }
    ]

    datasets = {
        "customers": test_customers,
        "orders": test_orders,
        "events": test_events,
        "daily_metrics": test_daily_metrics
    }

    result = writer.export_datasets(
        datasets=datasets,
        metadata={
            "simulation_days": 7
        }
    )

    print("\nExport completed successfully.")

    for dataset_name, summary in result["datasets"].items():
        print(
            f"{dataset_name}: "
            f"{summary['record_count']} records"
        )

    print(f"\nManifest: {result['manifest']}")