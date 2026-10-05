import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = (
    PROJECT_ROOT
    / "schema"
    / "simulation_dataset_schemas.json"
)


class SimulationDatasetSchemaValidator:

    def __init__(self, schema_path=SCHEMA_PATH):

        with open(
            schema_path,
            "r",
            encoding="utf-8"
        ) as file:
            self.schema = json.load(file)

        self.errors = []
        self.checks = {}

    # ---------------------------------------------------------
    # TYPE CHECKING
    # ---------------------------------------------------------

    def _matches_type(self, value, expected_type):

        if expected_type == "string":
            return isinstance(value, str)

        if expected_type == "integer":
            return (
                isinstance(value, int)
                and not isinstance(value, bool)
            )

        if expected_type == "number":
            return (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
            )

        if expected_type == "boolean":
            return isinstance(value, bool)

        if expected_type == "array":
            return isinstance(value, list)

        if expected_type == "object":
            return isinstance(value, dict)

        if expected_type == "string_or_null":
            return (
                value is None
                or isinstance(value, str)
            )

        if expected_type == "integer_or_null":
            return (
                value is None
                or (
                    isinstance(value, int)
                    and not isinstance(value, bool)
                )
            )

        return False

    # ---------------------------------------------------------
    # VALUE VALIDATION
    # ---------------------------------------------------------

    def _validate_value(
        self,
        value,
        rule,
        field_path
    ):

        expected_type = rule.get("type")

        if not self._matches_type(
            value,
            expected_type
        ):
            self.errors.append(
                f"{field_path}: expected "
                f"{expected_type}, got "
                f"{type(value).__name__}"
            )
            return

        # ---------------------------------------------
        # Nested object validation
        # ---------------------------------------------

        if (
            expected_type == "object"
            and isinstance(value, dict)
        ):

            nested_fields = rule.get(
                "fields",
                {}
            )

            for nested_name, nested_rule in nested_fields.items():

                nested_path = (
                    f"{field_path}.{nested_name}"
                )

                if nested_name not in value:
                    self.errors.append(
                        f"{nested_path}: missing required field"
                    )
                    continue

                self._validate_value(
                    value[nested_name],
                    nested_rule,
                    nested_path
                )

    # ---------------------------------------------------------
    # RECORD VALIDATION
    # ---------------------------------------------------------

    def _validate_record(
        self,
        dataset_name,
        record,
        record_index,
        dataset_schema
    ):

        if not isinstance(record, dict):
            self.errors.append(
                f"{dataset_name}[{record_index}]: "
                f"record must be an object"
            )
            return

        required_fields = dataset_schema.get(
            "required_fields",
            {}
        )

        optional_fields = dataset_schema.get(
            "optional_fields",
            {}
        )

        # ---------------------------------------------
        # Required fields
        # ---------------------------------------------

        for field_name, rule in required_fields.items():

            field_path = (
                f"{dataset_name}"
                f"[{record_index}]"
                f".{field_name}"
            )

            if field_name not in record:
                self.errors.append(
                    f"{field_path}: missing required field"
                )
                continue

            self._validate_value(
                record[field_name],
                rule,
                field_path
            )

        # ---------------------------------------------
        # Optional fields
        # ---------------------------------------------

        for field_name, rule in optional_fields.items():

            if field_name not in record:
                continue

            field_path = (
                f"{dataset_name}"
                f"[{record_index}]"
                f".{field_name}"
            )

            self._validate_value(
                record[field_name],
                rule,
                field_path
            )

    # ---------------------------------------------------------
    # DATASET VALIDATION
    # ---------------------------------------------------------

    def validate_datasets(self, datasets):

        self.errors = []
        self.checks = {}

        schema_datasets = self.schema.get(
            "datasets",
            {}
        )

        for dataset_name, dataset_schema in schema_datasets.items():

            records = datasets.get(
                dataset_name
            )

            if records is None:
                self.errors.append(
                    f"Missing dataset: {dataset_name}"
                )
                continue

            dataset_error_start = len(
                self.errors
            )

            for index, record in enumerate(records):

                self._validate_record(
                    dataset_name=dataset_name,
                    record=record,
                    record_index=index,
                    dataset_schema=dataset_schema
                )

            dataset_errors = (
                len(self.errors)
                - dataset_error_start
            )

            self.checks[dataset_name] = {
                "records_checked": len(records),
                "errors": dataset_errors,
                "passed": dataset_errors == 0
            }

        return {
            "passed": len(self.errors) == 0,
            "error_count": len(self.errors),
            "errors": self.errors,
            "checks": self.checks
        }

    # ---------------------------------------------------------
    # SIMULATION STATE VALIDATION
    # ---------------------------------------------------------

    def validate_state(self, state):

        datasets = {
            "customers": list(
                state.customers.values()
            ),

            "orders": list(
                state.orders.values()
            ),

            "events": list(
                state.events.values()
            ),

            "daily_metrics": list(
                state.daily_metrics
            ),

            "behavior_history": list(
                state.behavior_history
            ),

            "conversion_history": list(
                state.conversion_history
            )
        }

        return self.validate_datasets(
            datasets
        )