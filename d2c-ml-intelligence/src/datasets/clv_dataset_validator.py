import numpy as np

from src.datasets.clv_dataset import (
    CLVDatasetBuilder
)


class CLVDatasetValidator:

    def __init__(self):

        self.builder = (
            CLVDatasetBuilder()
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
        self._validate_duplicates()
        self._validate_target()
        self._validate_label_windows()
        self._validate_target_against_source()
        self._validate_no_future_leakage()
        self._validate_target_distribution()

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
            "future_customer_value_30d"
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
    # TARGET
    # ======================================================

    def _validate_target(self):

        target = (
            self.dataset[
                "future_customer_value_30d"
            ]
        )

        if target.isna().any():

            self.errors.append(
                "CLV target contains "
                "missing values."
            )

        if (target < 0).any():

            self.errors.append(
                "CLV target contains "
                "negative values."
            )

        if not np.isfinite(
            target.to_numpy(
                dtype=float
            )
        ).all():

            self.errors.append(
                "CLV target contains "
                "non-finite values."
            )

    # ======================================================
    # LABEL WINDOW
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
                    f"target window ends at "
                    f"{future_end}, beyond source "
                    f"day {max_source_day}."
                )

    # ======================================================
    # SOURCE TARGET RECONCILIATION
    # ======================================================

    def _validate_target_against_source(
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

            expected_customer_value = (
                future_orders
                .groupby(
                    "customer_id"
                )[
                    "gross_amount"
                ]
                .sum()
                .to_dict()
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
                .map(
                    expected_customer_value
                )
                .fillna(0.0)
                .to_numpy(
                    dtype=float
                )
            )

            actual = (
                snapshot[
                    "future_customer_value_30d"
                ]
                .to_numpy(
                    dtype=float
                )
            )

            if not np.allclose(
                expected,
                actual,
                rtol=1e-6,
                atol=1e-6
            ):

                mismatch_count = (
                    ~np.isclose(
                        expected,
                        actual,
                        rtol=1e-6,
                        atol=1e-6
                    )
                ).sum()

                self.errors.append(
                    f"Snapshot {snapshot_day}: "
                    f"{mismatch_count} CLV targets "
                    "do not match source orders."
                )

            expected_total = (
                future_orders[
                    "gross_amount"
                ]
                .sum()
            )

            actual_total = (
                snapshot[
                    "future_customer_value_30d"
                ]
                .sum()
            )

            if not np.isclose(
                expected_total,
                actual_total,
                rtol=1e-6,
                atol=1e-6
            ):

                self.errors.append(
                    f"Snapshot {snapshot_day}: "
                    f"target revenue {actual_total} "
                    "does not match source revenue "
                    f"{expected_total}."
                )

    # ======================================================
    # LEAKAGE
    # ======================================================

    def _validate_no_future_leakage(
        self
    ):

        forbidden_columns = {
            "future_order_count",
            "future_value_positive",
            "future_revenue",
            "future_orders",
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
    # DISTRIBUTION
    # ======================================================

    def _validate_target_distribution(
        self
    ):

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

            target = (
                snapshot[
                    "future_customer_value_30d"
                ]
            )

            positive_count = (
                target > 0
            ).sum()

            zero_count = (
                target == 0
            ).sum()

            if positive_count == 0:

                self.errors.append(
                    f"Snapshot {snapshot_day}: "
                    "no positive CLV targets."
                )

            if zero_count == 0:

                self.errors.append(
                    f"Snapshot {snapshot_day}: "
                    "no zero CLV targets."
                )


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 70)
    print(
        "PHASE 7 - CLV DATASET VALIDATION"
    )
    print("=" * 70)

    validator = (
        CLVDatasetValidator()
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
        "\nPositive-value customers "
        "by snapshot:"
    )

    print(
        validator.dataset
        .assign(
            positive_value=(
                validator.dataset[
                    "future_customer_value_30d"
                ]
                > 0
            ).astype(int)
        )
        .groupby(
            "snapshot_day"
        )[
            "positive_value"
        ]
        .sum()
    )

    print(
        "\nTarget revenue by snapshot:"
    )

    print(
        validator.dataset
        .groupby(
            "snapshot_day"
        )[
            "future_customer_value_30d"
        ]
        .sum()
    )

    print(
        "\nValidation result:"
    )

    print(result)

    if not result[
        "passed"
    ]:

        raise AssertionError(
            "CLV dataset "
            "validation failed."
        )

    print(
        "\nCLV DATASET "
        "VALIDATION PASSED."
    )
    