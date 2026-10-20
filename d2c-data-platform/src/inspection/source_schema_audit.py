
import csv
import json

from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_PATH = (
    PROJECT_ROOT
    / "config"
    / "platform_config.json"
)


def load_config():

    with CONFIG_PATH.open(
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


def inspect_csv(path, expected_rows):

    if not path.is_file():
        raise FileNotFoundError(
            f"Missing source file: {path}"
        )

    null_counts = Counter()
    row_count = 0

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        columns = reader.fieldnames

        if not columns:
            raise ValueError(
                f"No header found: {path}"
            )

        if len(columns) != len(set(columns)):
            raise ValueError(
                f"Duplicate column names: {path}"
            )

        for row in reader:

            row_count += 1

            if None in row:
                raise ValueError(
                    f"Unexpected extra fields in {path}"
                )

            for column in columns:

                if row[column] is None:
                    raise ValueError(
                        f"Missing field in {path}: {column}"
                    )

                if row[column] == "":
                    null_counts[column] += 1

    if row_count != expected_rows:

        raise ValueError(
            f"{path.name}: expected {expected_rows} "
            f"rows, found {row_count}"
        )

    return {
        "rows": row_count,
        "column_count": len(columns),
        "columns": columns,
        "observed_blank_counts": dict(null_counts)
    }


def main():

    print("=" * 70)
    print("PHASE 8 - SOURCE SCHEMA AUDIT")
    print("=" * 70)

    config = load_config()

    source_directory = (
        PROJECT_ROOT
        / config["source"]["dataset_path"]
    ).resolve()

    if not source_directory.is_dir():
        raise FileNotFoundError(
            f"Dataset directory not found: {source_directory}"
        )

    print("\nSource run:")
    print(config["source"]["run_id"])

    print("\nSource directory:")
    print(source_directory)

    profile = {
        "schema_version": config["schema_version"],
        "source_run_id": config["source"]["run_id"],
        "datasets": {}
    }

    for name, expected_rows in (
        config["expected_datasets"].items()
    ):

        path = source_directory / f"{name}.csv"

        result = inspect_csv(
            path,
            expected_rows
        )

        profile["datasets"][name] = result

        print(f"\n{name.upper()}")
        print(f"Rows: {result['rows']:,}")
        print(f"Columns: {result['column_count']}")
        print("Column names:")
        print(result["columns"])
        print(
            "Observed blank fields:",
            result["observed_blank_counts"]
        )

    product_path = (
        PROJECT_ROOT
        / config["source"]["product_master_path"]
    ).resolve()

    with product_path.open(
        "r",
        encoding="utf-8"
    ) as file:

        products = json.load(file)

    if not isinstance(products, list):
        raise ValueError(
            "Product master must be a JSON list."
        )

    if len(products) != 29:
        raise ValueError(
            f"Expected 29 products, found {len(products)}"
        )

    profile["product_master"] = {
        "rows": len(products),
        "columns": (
            list(products[0].keys())
            if products else []
        )
    }

    print("\nPRODUCT MASTER")
    print(f"Rows: {len(products)}")

    print("\nColumns:")
    print(profile["product_master"]["columns"])

    output_path = (
        PROJECT_ROOT
        / "reports"
        / "source_schema_profile.json"
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with output_path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            profile,
            file,
            indent=2
        )

    print("\nSchema profile saved:")
    print(output_path)

    print(
        "\nSOURCE SCHEMA AUDIT PASSED."
    )


if __name__ == "__main__":
    main()
