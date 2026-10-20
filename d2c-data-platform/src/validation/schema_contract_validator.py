
import csv
import json
import re

from decimal import Decimal, InvalidOperation
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


class SchemaContractValidator:

    def __init__(self):

        self.config = load_json(
            PROJECT_ROOT / "config" / "platform_config.json"
        )

        self.schema = load_json(
            PROJECT_ROOT / "schemas" / "canonical_schema.json"
        )["datasets"]

        self.profile = load_json(
            PROJECT_ROOT / "reports" / "source_schema_profile.json"
        )

        self.source_dir = (
            PROJECT_ROOT / self.config["source"]["dataset_path"]
        ).resolve()

    # ==================================================
    # TYPE VALIDATION
    # ==================================================

    def normalize_value(self, value, field_type):

        nullable = field_type.startswith("nullable_")

        if value is None or value == "":
            if nullable:
                return None
            raise ValueError("Required value is missing")

        kind = (
            field_type.removeprefix("nullable_")
            if nullable else field_type
        )

        if kind == "string":

            if not isinstance(value, str) or not value.strip():
                raise ValueError("Expected nonempty string")

            return value

        if kind == "integer":

            if isinstance(value, bool):
                raise ValueError("Boolean is not an integer")

            if isinstance(value, int):
                return value

            if (
                isinstance(value, str)
                and re.fullmatch(r"-?\d+", value)
            ):
                return int(value)

            raise ValueError("Expected integer")

        if kind == "number":

            if isinstance(value, bool):
                raise ValueError("Boolean is not a number")

            try:
                number = Decimal(str(value))
            except (InvalidOperation, ValueError):
                raise ValueError("Expected number")

            if not number.is_finite():
                raise ValueError("Number must be finite")

            return number

        if kind in ("json_array", "json_object"):

            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    raise ValueError("Malformed JSON")

            expected_type = (
                list if kind == "json_array" else dict
            )

            if not isinstance(value, expected_type):
                raise ValueError(f"Expected {kind}")

            return value

        raise ValueError(
            f"Unsupported schema type: {field_type}"
        )

    # ==================================================
    # VALIDATE ONE DATASET
    # ==================================================

    def validate_dataset(
        self,
        name,
        records,
        observed_columns,
        expected_rows
    ):

        contract = self.schema[name]
        fields = contract["fields"]
        primary_key = contract["primary_key"]

        issues = []
        issue_count = 0
        seen_keys = set()
        row_count = 0

        def add_issue(message):
            nonlocal issue_count

            issue_count += 1

            # Keep only the first 10 examples.
            if len(issues) < 10:
                issues.append(message)

        if observed_columns != list(fields):
            add_issue(
                "Column names/order do not match the contract"
            )

        for row_number, row in enumerate(records, start=1):

            row_count += 1

            if not isinstance(row, dict):
                add_issue(f"Row {row_number}: not an object")
                continue

            if set(row) != set(fields):
                add_issue(
                    f"Row {row_number}: missing or extra fields"
                )

            normalized = {}

            for column, field_type in fields.items():

                if column not in row:
                    continue

                try:
                    normalized[column] = self.normalize_value(
                        row[column],
                        field_type
                    )

                except ValueError as error:
                    add_issue(
                        f"Row {row_number}, "
                        f"field '{column}': {error}"
                    )

            # Check primary-key uniqueness only when
            # all key values are valid.
            if all(
                key in normalized
                and normalized[key] is not None
                for key in primary_key
            ):

                key_values = tuple(
                    normalized[key] for key in primary_key
                )

                if key_values in seen_keys:
                    add_issue(
                        f"Row {row_number}: "
                        f"duplicate primary key {key_values}"
                    )
                else:
                    seen_keys.add(key_values)

        if row_count != expected_rows:
            add_issue(
                f"Expected {expected_rows} rows, "
                f"found {row_count}"
            )

        return {
            "dataset": name,
            "rows": row_count,
            "columns": len(fields),
            "primary_key": primary_key,
            "issue_count": issue_count,
            "issue_examples": issues,
            "passed": issue_count == 0
        }

    # ==================================================
    # VALIDATE ALL SOURCE DATA
    # ==================================================

    def validate_all(self):

        results = {}

        for name, expected_rows in (
            self.config["expected_datasets"].items()
        ):

            path = self.source_dir / f"{name}.csv"

            with path.open(
                "r",
                encoding="utf-8-sig",
                newline=""
            ) as file:

                reader = csv.DictReader(file)

                results[name] = self.validate_dataset(
                    name=name,
                    records=reader,
                    observed_columns=reader.fieldnames or [],
                    expected_rows=expected_rows
                )

        # Product master is stored in JSON, not CSV.
        product_path = (
            PROJECT_ROOT
            / self.config["source"]["product_master_path"]
        ).resolve()

        products = load_json(product_path)

        if not isinstance(products, list):
            raise ValueError(
                "Product master must be a JSON list"
            )

        product_columns = list(
            self.schema["product_master"]["fields"]
        )

        results["product_master"] = self.validate_dataset(
            name="product_master",
            records=products,
            observed_columns=product_columns,
            expected_rows=self.profile["product_master"]["rows"]
        )

        return results


# ======================================================
# MAIN
# ======================================================

if __name__ == "__main__":

    print("=" * 70)
    print("PHASE 8 - SCHEMA CONTRACT VALIDATION")
    print("=" * 70)

    validator = SchemaContractValidator()

    results = validator.validate_all()

    passed = 0

    for name, result in results.items():

        status = "PASS" if result["passed"] else "FAIL"

        print(f"\n{name.upper()}")
        print(f"Rows: {result['rows']:,}")
        print(f"Columns: {result['columns']}")
        print(f"Primary key: {result['primary_key']}")
        print(f"Issues: {result['issue_count']}")
        print(f"Status: {status}")

        if result["passed"]:
            passed += 1

        for issue in result["issue_examples"]:
            print("  ERROR:", issue)

    print("\n" + "=" * 70)
    print(f"DATASETS PASSED: {passed}/{len(results)}")

    if passed != len(results):
        raise SystemExit(
            "SCHEMA CONTRACT VALIDATION FAILED."
        )

    print("\nSCHEMA CONTRACT VALIDATION PASSED.")
