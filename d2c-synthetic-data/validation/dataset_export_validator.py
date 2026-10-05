from pathlib import Path
import csv
import json

def count_csv_rows(file_path):
    with file_path.open(
        mode="r",
        encoding="utf-8",
        newline=""
    ) as csv_file:

        reader = csv.DictReader(csv_file)

        return sum(1 for _ in reader)

def validate_required_column(file_path, required_column):
    with file_path.open(
        mode="r",
        encoding="utf-8",
        newline=""
    ) as csv_file:

        reader = csv.DictReader(csv_file)

        if required_column not in reader.fieldnames:
            raise AssertionError(
                f"{file_path.name}: missing required column "
                f"'{required_column}'"
            )

def load_manifest(file_path):
    with file_path.open(
        mode="r",
        encoding="utf-8"
    ) as manifest_file:

        return json.load(manifest_file)

def validate_export(run_directory):
    run_directory = Path(run_directory)

    expected_files = [
        "customers.csv",
        "customers.jsonl",
        "orders.csv",
        "orders.jsonl",
        "events.csv",
        "events.jsonl",
        "daily_metrics.csv",
        "daily_metrics.jsonl",
        "behavior_history.csv",
        "behavior_history.jsonl",
        "conversion_history.csv",
        "conversion_history.jsonl",
        "simulation_manifest.json",
    ]

    print("=" * 60)
    print("DATASET EXPORT VALIDATION")
    print("=" * 60)

    for filename in expected_files:
        file_path = run_directory / filename

        if not file_path.exists():
            raise AssertionError(
                f"Missing export file: {filename}"
            )

        print(f"FOUND: {filename}")

    print("\nFile existence validation PASSED.")

    expected_counts = {
        "customers.csv": 10,
        "orders.csv": 6,
        "events.csv": 29,
        "daily_metrics.csv": 7,
        "behavior_history.csv": 23,
        "conversion_history.csv": 13,
    }

    print("\nChecking CSV record counts...")

    for filename, expected_count in expected_counts.items():

        file_path = run_directory / filename

        actual_count = count_csv_rows(
            file_path
        )

        if actual_count != expected_count:
            raise AssertionError(
                f"{filename}: expected "
                f"{expected_count} records, "
                f"found {actual_count}"
            )

        print(
            f"PASSED: {filename} "
            f"({actual_count} records)"
        )

    print("\nCSV row-count validation PASSED.")

    print("\nChecking required ID columns...")

    required_columns = {
        "customers.csv": "customer_id",
        "orders.csv": "order_id",
        "events.csv": "event_id",
    }

    for filename, required_column in required_columns.items():

        file_path = run_directory / filename

        validate_required_column(
            file_path,
            required_column
        )

        print(
            f"PASSED: {filename} "
            f"contains '{required_column}'"
        )

    print("\nRequired ID-column validation PASSED.")

    print("\nChecking manifest consistency...")

    manifest_path = run_directory / "simulation_manifest.json"

    manifest = load_manifest(
        manifest_path
    )

    for dataset_name, dataset_info in manifest["datasets"].items():

        expected_count = dataset_info["record_count"]

        csv_filename = f"{dataset_name}.csv"
        csv_path = run_directory / csv_filename

        if csv_path.exists():

            actual_count = count_csv_rows(
                csv_path
            )

            if actual_count != expected_count:
                raise AssertionError(
                    f"{dataset_name}: manifest says "
                    f"{expected_count}, CSV contains "
                    f"{actual_count}"
                )

            print(
                f"PASSED: {dataset_name} "
                f"manifest count = {actual_count}"
            )

    print("\nManifest consistency validation PASSED.")

if __name__ == "__main__":
    validate_export(
        "data/generated/simulation_run_20260919_181338"
    )