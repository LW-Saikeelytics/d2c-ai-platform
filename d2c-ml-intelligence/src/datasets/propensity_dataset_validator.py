import pandas as pd

from src.datasets.propensity_dataset import (
    PropensityDatasetBuilder
)


class PropensityDatasetValidator:

    def __init__(self):

        self.builder = (
            PropensityDatasetBuilder()
        )

        self.dataset = (
            self.builder.build_dataset()
        )

        self.errors = []

    # ======================================================
    # MAIN
    # ======================================================

    def validate(self):

        self._validate_structure()
        self._validate_target_values()
        self._validate_duplicates()
        self._validate_label_windows()
        self._validate_labels_against_source()
        self._validate_no_future_leakage()
        self._validate_class_balance()

        return {
            "passed": len(self.errors) == 0,
            "error_count": len(self.errors),
            "errors": self.errors
        }

    # ======================================================
    # STRUCTURE
    # ======================================================

    def _validate_structure(self):

        expected_rows = (
            10000
            *
            len(
                self.builder.snapshot_days
            )
        )

        if len(self.dataset) != expected_rows:

            self.errors.append(
                f"Expected {expected_rows} rows, "
                f"found {len(self.dataset)}."
            )

        required_columns = {
            "customer_id",
            "snapshot_day",
            "purchase_propensity_label"
        }

        missing = (
            required_columns
            -
            set(
                self.dataset.columns
            )
        )

        if missing:

            self.errors.append(
                "Missing required columns: "
                f"{sorted(missing)}"
            )

    # ======================================================
    # TARGET
    # ======================================================

    def _validate_target_values(self):

        targets = set(
            self.dataset[
                "purchase_propensity_label"
            ]
            .dropna()
            .unique()
            .tolist()
        )

        if not targets.issubset(
            {0, 1}
        ):

            self.errors.append(
                "Invalid target values found: "
                f"{sorted(targets)}"
            )

        if self.dataset[
            "purchase_propensity_label"
        ].isna().any():

            self.errors.append(
                "Target contains missing values."
            )

    # ======================================================
    # DUPLICATES
    # ======================================================

    def _validate_duplicates(self):

        duplicates = (
            self.dataset
            .duplicated(
                subset=[
                    "customer_id",
                    "snapshot_day"
                ]
            )
            .sum()
        )

        if duplicates > 0:

            self.errors.append(
                f"Found {duplicates} duplicate "
                "customer/snapshot rows."
            )

    # ======================================================
    # LABEL WINDOWS
    # ======================================================

    def _validate_label_windows(self):

        max_source_day = (
            self.builder.orders[
                "simulation_day"
            ]
            .max()
        )

        for snapshot_day in (
            self.builder.snapshot_days
        ):

            future_end = (
                snapshot_day
                +
                self.builder.label_window_days
            )

            if future_end > max_source_day:

                self.errors.append(
                    f"Snapshot {snapshot_day}: "
                    f"label window ends at "
                    f"{future_end}, beyond source "
                    f"day {max_source_day}."
                )

    # ======================================================
    # SOURCE LABEL RECONCILIATION
    # ======================================================

    def _validate_labels_against_source(
        self
    ):

        for snapshot_day in (
            self.builder.snapshot_days
        ):

            future_start = (
                snapshot_day + 1
            )

            future_end = (
                snapshot_day
                +
                self.builder.label_window_days
            )

            future_orders = (
                self.builder.orders[
                    (
                        self.builder.orders[
                            "simulation_day"
                        ]
                        >= future_start
                    )
                    &
                    (
                        self.builder.orders[
                            "simulation_day"
                        ]
                        <= future_end
                    )
                ]
            )

            purchasing_customers = set(
                future_orders[
                    "customer_id"
                ]
                .unique()
                .tolist()
            )

            snapshot = (
                self.dataset[
                    self.dataset[
                        "snapshot_day"
                    ]
                    == snapshot_day
                ]
            )

            expected = (
                snapshot[
                    "customer_id"
                ]
                .isin(
                    purchasing_customers
                )
                .astype(int)
            )

            actual = (
                snapshot[
                    "purchase_propensity_label"
                ]
            )

            mismatches = (
                expected.values
                !=
                actual.values
            ).sum()

            if mismatches > 0:

                self.errors.append(
                    f"Snapshot {snapshot_day}: "
                    f"{mismatches} target labels "
                    "do not match source orders."
                )

    # ======================================================
    # LEAKAGE
    # ======================================================

    def _validate_no_future_leakage(
        self
    ):

        forbidden_columns = {
            "future_order_count",
            "future_revenue",
            "future_purchase",
            "future_conversion",
            "conversion_probability",
            "purchase_propensity",
            "status",
            "lifetime_orders",
            "lifetime_spend",
            "last_order_day"
        }

        leaked = (
            forbidden_columns
            &
            set(
                self.dataset.columns
            )
        )

        if leaked:

            self.errors.append(
                "Potential leakage columns found: "
                f"{sorted(leaked)}"
            )

        activity_invalid = (
            self.dataset[
                "hist_last_activity_day"
            ]
            .notna()
            &
            (
                self.dataset[
                    "hist_last_activity_day"
                ]
                >
                self.dataset[
                    "snapshot_day"
                ]
            )
        )

        if activity_invalid.any():

            self.errors.append(
                "Historical behavior contains "
                "future information."
            )

        order_invalid = (
            self.dataset[
                "hist_last_order_day"
            ]
            .notna()
            &
            (
                self.dataset[
                    "hist_last_order_day"
                ]
                >
                self.dataset[
                    "snapshot_day"
                ]
            )
        )

        if order_invalid.any():

            self.errors.append(
                "Historical orders contain "
                "future information."
            )

    # ======================================================
    # CLASS BALANCE
    # ======================================================

    def _validate_class_balance(self):

        for snapshot_day in (
            self.builder.snapshot_days
        ):

            snapshot = (
                self.dataset[
                    self.dataset[
                        "snapshot_day"
                    ]
                    == snapshot_day
                ]
            )

            classes = set(
                snapshot[
                    "purchase_propensity_label"
                ]
                .unique()
                .tolist()
            )

            if classes != {0, 1}:

                self.errors.append(
                    f"Snapshot {snapshot_day}: "
                    "both target classes are "
                    "not represented."
                )

            positive_rate = (
                snapshot[
                    "purchase_propensity_label"
                ]
                .mean()
            )

            if (
                positive_rate <= 0.01
                or positive_rate >= 0.99
            ):

                self.errors.append(
                    f"Snapshot {snapshot_day}: "
                    f"extreme positive rate "
                    f"{positive_rate:.4f}."
                )


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 70)
    print(
        "PHASE 7 - PROPENSITY DATASET VALIDATION"
    )
    print("=" * 70)

    validator = (
        PropensityDatasetValidator()
    )

    result = (
        validator.validate()
    )

    print(
        f"\nRows validated: "
        f"{len(validator.dataset):,}"
    )

    print(
        f"Columns validated: "
        f"{len(validator.dataset.columns)}"
    )

    print(
        "\nTarget distribution:"
    )

    print(
        validator.dataset[
            "purchase_propensity_label"
        ]
        .value_counts()
        .sort_index()
    )

    print(
        "\nPurchase rate by snapshot:"
    )

    print(
        validator.dataset
        .groupby(
            "snapshot_day"
        )[
            "purchase_propensity_label"
        ]
        .mean()
    )

    print(
        "\nValidation result:"
    )

    print(result)

    if not result[
        "passed"
    ]:

        raise AssertionError(
            "Propensity dataset "
            "validation failed."
        )

    print(
        "\nPROPENSITY DATASET "
        "VALIDATION PASSED."
    )