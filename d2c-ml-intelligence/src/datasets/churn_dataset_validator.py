import numpy as np
import pandas as pd

from src.datasets.churn_dataset import (
    ChurnDatasetBuilder
)


class ChurnDatasetValidator:

    def __init__(self):

        self.builder = (
            ChurnDatasetBuilder()
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
        self._validate_eligibility()
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

        required_columns = {
            "customer_id",
            "snapshot_day",
            "churn_label"
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

        if len(self.dataset) == 0:

            self.errors.append(
                "Churn dataset is empty."
            )

    # ======================================================
    # TARGET
    # ======================================================

    def _validate_target_values(self):

        unique_targets = set(
            self.dataset[
                "churn_label"
            ]
            .dropna()
            .unique()
            .tolist()
        )

        if not unique_targets.issubset(
            {0, 1}
        ):

            self.errors.append(
                "churn_label contains "
                f"invalid values: "
                f"{sorted(unique_targets)}"
            )

        if self.dataset[
            "churn_label"
        ].isna().any():

            self.errors.append(
                "churn_label contains "
                "missing values."
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
    # ELIGIBILITY
    # ======================================================

    def _validate_eligibility(self):

        historical_behavior = (
            self.dataset[
                "hist_product_view_count"
            ]
            +
            self.dataset[
                "hist_add_to_cart_count"
            ]
            +
            self.dataset[
                "hist_purchase_intent_count"
            ]
            +
            self.dataset[
                "hist_cart_abandonment_count"
            ]
        )

        invalid = (
            (historical_behavior <= 0)
            &
            (
                self.dataset[
                    "hist_order_count"
                ]
                <= 0
            )
        )

        if invalid.any():

            self.errors.append(
                "Dataset contains customers "
                "with no historical engagement."
            )

    # ======================================================
    # LABEL WINDOW
    # ======================================================

    def _validate_label_windows(self):

        max_source_day = max(
            self.builder.behavior[
                "simulation_day"
            ].max(),

            self.builder.orders[
                "simulation_day"
            ].max()
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

            # ----------------------------------------------
            # BEHAVIOR ACTIVITY
            # ----------------------------------------------

            behavior_customers = set(
                self.builder.behavior[
                    (
                        self.builder.behavior[
                            "simulation_day"
                        ]
                        >= future_start
                    )
                    &
                    (
                        self.builder.behavior[
                            "simulation_day"
                        ]
                        <= future_end
                    )
                ][
                    "customer_id"
                ]
                .unique()
                .tolist()
            )

            # ----------------------------------------------
            # ORDER ACTIVITY
            # ----------------------------------------------

            order_customers = set(
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
                ][
                    "customer_id"
                ]
                .unique()
                .tolist()
            )

            active_customers = (
                behavior_customers
                |
                order_customers
            )

            snapshot = (
                self.dataset[
                    self.dataset[
                        "snapshot_day"
                    ]
                    == snapshot_day
                ]
            )

            expected_labels = (
                ~snapshot[
                    "customer_id"
                ].isin(
                    active_customers
                )
            ).astype(int)

            actual_labels = (
                snapshot[
                    "churn_label"
                ]
            )

            if not (
                expected_labels.values
                ==
                actual_labels.values
            ).all():

                mismatch_count = (
                    expected_labels.values
                    !=
                    actual_labels.values
                ).sum()

                self.errors.append(
                    f"Snapshot {snapshot_day}: "
                    f"{mismatch_count} churn labels "
                    "do not match source activity."
                )

    # ======================================================
    # FUTURE LEAKAGE
    # ======================================================

    def _validate_no_future_leakage(
        self
    ):

        forbidden_columns = {
            "future_active_days",
            "future_orders",
            "future_revenue",
            "future_events",
            "future_behavior_days",
            "status",
            "lifetime_orders",
            "lifetime_spend",
            "last_order_day",
            "conversion_probability"
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
                "Potential leakage columns "
                f"found: {sorted(leaked)}"
            )

        # Historical activity must never
        # occur after the snapshot.

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
                "Historical activity contains "
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
                    "churn_label"
                ]
                .unique()
                .tolist()
            )

            if classes != {0, 1}:

                self.errors.append(
                    f"Snapshot {snapshot_day}: "
                    "both churn classes are "
                    "not represented."
                )

            churn_rate = (
                snapshot[
                    "churn_label"
                ]
                .mean()
            )

            if (
                churn_rate <= 0.05
                or churn_rate >= 0.95
            ):

                self.errors.append(
                    f"Snapshot {snapshot_day}: "
                    f"extreme churn rate "
                    f"{churn_rate:.4f}."
                )


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 70)
    print(
        "PHASE 7 - CHURN DATASET VALIDATION"
    )
    print("=" * 70)

    validator = (
        ChurnDatasetValidator()
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
        "\nClass distribution:"
    )

    print(
        validator.dataset[
            "churn_label"
        ]
        .value_counts()
        .sort_index()
    )

    print(
        "\nChurn rate by snapshot:"
    )

    print(
        validator.dataset
        .groupby(
            "snapshot_day"
        )[
            "churn_label"
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
            "Churn dataset "
            "validation failed."
        )

    print(
        "\nCHURN DATASET "
        "VALIDATION PASSED."
    )
    