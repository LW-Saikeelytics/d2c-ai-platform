from pathlib import Path
from datetime import datetime
import csv
import json


class AnalyticsDatasetWriter:

    def __init__(self, run_directory):

        self.run_directory = Path(
            run_directory
        )

        self.analytics_directory = (
            self.run_directory
            / "analytics"
        )

        self.analytics_directory.mkdir(
            parents=True,
            exist_ok=True
        )

    # ---------------------------------------------------------
    # FLAT RECORD CHECK
    # ---------------------------------------------------------

    def _validate_flat_record(
        self,
        table_name,
        record
    ):

        if not isinstance(record, dict):
            raise ValueError(
                f"{table_name}: "
                f"analytics row must be a dictionary"
            )

        for field_name, value in record.items():

            if isinstance(
                value,
                (dict, list, tuple, set)
            ):
                raise ValueError(
                    f"{table_name}.{field_name}: "
                    f"nested values are not BI-friendly"
                )

    # ---------------------------------------------------------
    # WRITE CSV
    # ---------------------------------------------------------

    def write_csv(
        self,
        table_name,
        records
    ):

        if not records:
            return None

        for record in records:
            self._validate_flat_record(
                table_name,
                record
            )

        fieldnames = []

        for record in records:
            for key in record:

                if key not in fieldnames:
                    fieldnames.append(
                        key
                    )

        file_path = (
            self.analytics_directory
            / f"{table_name}.csv"
        )

        with file_path.open(
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames
            )

            writer.writeheader()
            writer.writerows(records)

        return file_path

    # ---------------------------------------------------------
    # EXPORT TABLES
    # ---------------------------------------------------------

    def export(self, analytics_tables):

        table_summary = {}

        for table_name, records in (
            analytics_tables.items()
        ):

            path = self.write_csv(
                table_name,
                records
            )

            columns = (
                list(records[0].keys())
                if records
                else []
            )

            table_summary[table_name] = {
                "record_count":
                    len(records),

                "columns":
                    columns,

                "file":
                    (
                        path.name
                        if path
                        else None
                    )
            }

        manifest = {
            "created_at":
                datetime.now().isoformat(),

            "table_count":
                len(analytics_tables),

            "tables":
                table_summary
        }

        manifest_path = (
            self.analytics_directory
            / "analytics_manifest.json"
        )

        with manifest_path.open(
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                manifest,
                file,
                indent=4,
                ensure_ascii=False,
                default=str
            )

        return {
            "analytics_directory":
                self.analytics_directory,

            "tables":
                table_summary,

            "manifest":
                manifest_path
        }