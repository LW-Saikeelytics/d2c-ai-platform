import csv
import json
import uuid

from datetime import (
    datetime,
    timezone
)

from pathlib import Path


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)


class ExperimentTracker:

    def __init__(
        self,
        output_dir=None
    ):

        if output_dir is None:

            output_dir = (
                PROJECT_ROOT
                / "experiments"
            )

        self.output_dir = (
            Path(
                output_dir
            )
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.jsonl_path = (
            self.output_dir
            / "experiment_log.jsonl"
        )

        self.csv_path = (
            self.output_dir
            / "experiment_log.csv"
        )

    # ======================================================
    # SERIALIZATION
    # ======================================================

    def _json_safe(
        self,
        value
    ):

        # Primitive values
        if value is None or isinstance(
            value,
            (
                str,
                int,
                float,
                bool
            )
        ):

            return value

        # Lists / tuples
        if isinstance(
            value,
            (
                list,
                tuple
            )
        ):

            return [
                self._json_safe(
                    item
                )
                for item in value
            ]

        # Dictionaries
        if isinstance(
            value,
            dict
        ):

            return {
                str(key):
                    self._json_safe(
                        item
                    )
                for key, item
                in value.items()
            }

        # NumPy / pandas scalar-like
        if hasattr(
            value,
            "item"
        ):

            try:

                return value.item()

            except Exception:

                pass

        return str(
            value
        )

    # ======================================================
    # CREATE RECORD
    # ======================================================

    def create_record(
        self,
        model_name,
        model_type,
        dataset,
        train_snapshot=None,
        validation_snapshot=None,
        test_snapshot=None,
        parameters=None,
        metrics=None,
        notes=None
    ):

        experiment_id = (
            "EXP-"
            +
            uuid.uuid4()
            .hex[:12]
            .upper()
        )

        timestamp = (
            datetime.now(
                timezone.utc
            )
            .isoformat()
        )

        record = {
            "experiment_id":
                experiment_id,

            "timestamp_utc":
                timestamp,

            "model_name":
                model_name,

            "model_type":
                model_type,

            "dataset":
                dataset,

            "train_snapshot":
                train_snapshot,

            "validation_snapshot":
                validation_snapshot,

            "test_snapshot":
                test_snapshot,

            "parameters":
                self._json_safe(
                    parameters or {}
                ),

            "metrics":
                self._json_safe(
                    metrics or {}
                ),

            "notes":
                notes
        }

        return record

    # ======================================================
    # WRITE JSONL
    # ======================================================

    def _append_jsonl(
        self,
        record
    ):

        with self.jsonl_path.open(
            "a",
            encoding="utf-8"
        ) as file:

            file.write(
                json.dumps(
                    record,
                    ensure_ascii=False
                )
            )

            file.write(
                "\n"
            )

    # ======================================================
    # WRITE CSV
    # ======================================================

    def _append_csv(
        self,
        record
    ):

        flat_record = {
            "experiment_id":
                record[
                    "experiment_id"
                ],

            "timestamp_utc":
                record[
                    "timestamp_utc"
                ],

            "model_name":
                record[
                    "model_name"
                ],

            "model_type":
                record[
                    "model_type"
                ],

            "dataset":
                record[
                    "dataset"
                ],

            "train_snapshot":
                record[
                    "train_snapshot"
                ],

            "validation_snapshot":
                record[
                    "validation_snapshot"
                ],

            "test_snapshot":
                record[
                    "test_snapshot"
                ],

            "parameters":
                json.dumps(
                    record[
                        "parameters"
                    ],
                    ensure_ascii=False
                ),

            "metrics":
                json.dumps(
                    record[
                        "metrics"
                    ],
                    ensure_ascii=False
                ),

            "notes":
                record[
                    "notes"
                ]
        }

        fieldnames = list(
            flat_record.keys()
        )

        write_header = (
            not self.csv_path.exists()
            or
            self.csv_path.stat().st_size
            == 0
        )

        with self.csv_path.open(
            "a",
            encoding="utf-8",
            newline=""
        ) as file:

            writer = (
                csv.DictWriter(
                    file,
                    fieldnames=fieldnames
                )
            )

            if write_header:

                writer.writeheader()

            writer.writerow(
                flat_record
            )

    # ======================================================
    # LOG EXPERIMENT
    # ======================================================

    def log_experiment(
        self,
        model_name,
        model_type,
        dataset,
        train_snapshot=None,
        validation_snapshot=None,
        test_snapshot=None,
        parameters=None,
        metrics=None,
        notes=None
    ):

        record = (
            self.create_record(
                model_name=model_name,
                model_type=model_type,
                dataset=dataset,
                train_snapshot=(
                    train_snapshot
                ),
                validation_snapshot=(
                    validation_snapshot
                ),
                test_snapshot=(
                    test_snapshot
                ),
                parameters=parameters,
                metrics=metrics,
                notes=notes
            )
        )

        self._append_jsonl(
            record
        )

        self._append_csv(
            record
        )

        return record

    # ======================================================
    # READ HISTORY
    # ======================================================

    def load_history(self):

        if not self.jsonl_path.exists():

            return []

        records = []

        with self.jsonl_path.open(
            "r",
            encoding="utf-8"
        ) as file:

            for line in file:

                line = (
                    line.strip()
                )

                if not line:

                    continue

                records.append(
                    json.loads(
                        line
                    )
                )

        return records


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 70)
    print(
        "PHASE 7 - EXPERIMENT TRACKER TEST"
    )
    print("=" * 70)

    tracker = (
        ExperimentTracker()
    )

    record = (
        tracker.log_experiment(
            model_name=(
                "tracker_smoke_test"
            ),

            model_type=(
                "test"
            ),

            dataset=(
                "synthetic_test"
            ),

            train_snapshot=30,
            validation_snapshot=45,
            test_snapshot=60,

            parameters={
                "parameter_a":
                    1,

                "parameter_b":
                    "test"
            },

            metrics={
                "metric_a":
                    0.75,

                "metric_b":
                    0.50
            },

            notes=(
                "Experiment tracker "
                "smoke test."
            )
        )
    )

    history = (
        tracker.load_history()
    )

    print(
        "\nExperiment ID:"
    )

    print(
        record[
            "experiment_id"
        ]
    )

    print(
        "\nJSONL path:"
    )

    print(
        tracker.jsonl_path
    )

    print(
        "\nCSV path:"
    )

    print(
        tracker.csv_path
    )

    print(
        "\nExperiments stored:"
    )

    print(
        len(history)
    )

    print(
        "\nLatest experiment:"
    )

    print(
        history[-1]
    )

    print(
        "\nEXPERIMENT TRACKER "
        "TEST PASSED."
    )