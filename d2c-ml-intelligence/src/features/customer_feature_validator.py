import numpy as np

from src.features.customer_features import (
    CustomerFeatureBuilder
)


class CustomerFeatureValidator:

    def __init__(self):

        self.builder = (
            CustomerFeatureBuilder()
        )

        self.features = (
            self.builder
            .build_all_snapshots()
        )

        self.errors = []

    def validate(self):

        self._validate_structure()
        self._validate_leakage_columns()
        self._validate_non_negative_values()
        self._validate_rates()
        self._validate_window_hierarchy()
        self._validate_historical_monotonicity()
        self._validate_temporal_consistency()
        self._validate_purchase_history()
        self._validate_average_order_value()

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
            len(
                self.builder.customers
            )
            *
            len(
                self.builder.snapshot_days
            )
        )

        if len(self.features) != expected_rows:

            self.errors.append(
                f"Expected {expected_rows} rows, "
                f"found {len(self.features)}."
            )

        duplicates = (
            self.features
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

        snapshot_counts = (
            self.features[
                "snapshot_day"
            ]
            .value_counts()
            .to_dict()
        )

        expected_per_snapshot = (
            len(
                self.builder.customers
            )
        )

        for snapshot_day in (
            self.builder.snapshot_days
        ):

            actual = snapshot_counts.get(
                snapshot_day,
                0
            )

            if actual != expected_per_snapshot:

                self.errors.append(
                    f"Snapshot {snapshot_day}: "
                    f"expected "
                    f"{expected_per_snapshot} rows, "
                    f"found {actual}."
                )

    # ======================================================
    # LEAKAGE
    # ======================================================

    def _validate_leakage_columns(self):

        forbidden_columns = {
            "lifetime_orders",
            "lifetime_spend",
            "last_order_day",
            "status"
        }

        leaked = (
            forbidden_columns
            &
            set(
                self.features.columns
            )
        )

        if leaked:

            self.errors.append(
                "Final-state customer columns "
                f"found in feature table: "
                f"{sorted(leaked)}"
            )

    # ======================================================
    # NON-NEGATIVE VALUES
    # ======================================================

    def _validate_non_negative_values(self):

        columns = [
            column
            for column
            in self.features.columns
            if (
                "_count" in column
                or "_active_days" in column
                or "_unique_" in column
                or "_total_spend" in column
                or "_total_quantity" in column
                or column
                in {
                    "customer_tenure_days",
                    "days_since_last_order",
                    "days_since_last_activity"
                }
            )
        ]

        for column in columns:

            values = (
                self.features[column]
                .dropna()
            )

            if (values < 0).any():

                self.errors.append(
                    f"Negative values found "
                    f"in {column}."
                )

    # ======================================================
    # FUNNEL RATES
    # ======================================================

    def _validate_rates(self):

        rate_columns = [
            "view_to_cart_rate",
            "cart_to_intent_rate",
            "cart_abandonment_rate"
        ]

        for column in rate_columns:

            invalid = (
                (
                    self.features[column]
                    < 0
                )
                |
                (
                    self.features[column]
                    > 1
                )
            )

            if invalid.any():

                self.errors.append(
                    f"Invalid probability/rate "
                    f"found in {column}."
                )

    # ======================================================
    # WINDOW CONSISTENCY
    # ======================================================

    def _validate_window_hierarchy(self):

        metrics = [
            "product_view_count",
            "add_to_cart_count",
            "purchase_intent_count",
            "cart_abandonment_count",
            "active_days",
            "unique_products",
            "unique_categories",
            "order_count",
            "total_spend",
            "total_quantity",
            "unique_products_purchased",
            "unique_categories_purchased"
        ]

        for metric in metrics:

            short_column = (
                f"last_7d_{metric}"
            )

            long_column = (
                f"last_30d_{metric}"
            )

            historical_column = (
                f"hist_{metric}"
            )

            if not all(
                column
                in self.features.columns
                for column in [
                    short_column,
                    long_column,
                    historical_column
                ]
            ):
                continue

            short_values = (
                self.features[
                    short_column
                ]
                .fillna(0)
            )

            long_values = (
                self.features[
                    long_column
                ]
                .fillna(0)
            )

            historical_values = (
                self.features[
                    historical_column
                ]
                .fillna(0)
            )

            if (
                short_values
                >
                long_values
            ).any():

                self.errors.append(
                    f"{short_column} exceeds "
                    f"{long_column}."
                )

            if (
                long_values
                >
                historical_values
            ).any():

                self.errors.append(
                    f"{long_column} exceeds "
                    f"{historical_column}."
                )

    # ======================================================
    # CUMULATIVE HISTORICAL FEATURES
    # ======================================================

    def _validate_historical_monotonicity(
        self
    ):

        cumulative_columns = [
            "hist_product_view_count",
            "hist_add_to_cart_count",
            "hist_purchase_intent_count",
            "hist_cart_abandonment_count",
            "hist_active_days",
            "hist_unique_products",
            "hist_unique_categories",
            "hist_order_count",
            "hist_total_spend",
            "hist_total_quantity",
            "hist_unique_products_purchased",
            "hist_unique_categories_purchased"
        ]

        ordered = (
            self.features
            .sort_values(
                [
                    "customer_id",
                    "snapshot_day"
                ]
            )
        )

        for column in cumulative_columns:

            differences = (
                ordered
                .groupby(
                    "customer_id"
                )[column]
                .diff()
                .dropna()
            )

            if (
                differences
                < 0
            ).any():

                self.errors.append(
                    f"Cumulative feature "
                    f"{column} decreased "
                    "between snapshots."
                )

    # ======================================================
    # TIME CONSISTENCY
    # ======================================================

    def _validate_temporal_consistency(self):

        activity_invalid = (
            self.features[
                "hist_last_activity_day"
            ]
            .notna()
            &
            (
                self.features[
                    "hist_last_activity_day"
                ]
                >
                self.features[
                    "snapshot_day"
                ]
            )
        )

        if activity_invalid.any():

            self.errors.append(
                "Historical activity contains "
                "future activity."
            )

        order_invalid = (
            self.features[
                "hist_last_order_day"
            ]
            .notna()
            &
            (
                self.features[
                    "hist_last_order_day"
                ]
                >
                self.features[
                    "snapshot_day"
                ]
            )
        )

        if order_invalid.any():

            self.errors.append(
                "Historical orders contain "
                "future orders."
            )

    # ======================================================
    # PURCHASE HISTORY FLAG
    # ======================================================

    def _validate_purchase_history(self):

        expected = (
            self.features[
                "hist_order_count"
            ]
            .fillna(0)
            > 0
        ).astype(int)

        actual = (
            self.features[
                "has_purchase_history"
            ]
        )

        if not (
            expected
            ==
            actual
        ).all():

            self.errors.append(
                "has_purchase_history is "
                "inconsistent with "
                "hist_order_count."
            )

    # ======================================================
    # AVERAGE ORDER VALUE
    # ======================================================

    def _validate_average_order_value(self):

        purchased = (
            self.features[
                self.features[
                    "hist_order_count"
                ]
                > 0
            ]
        )

        expected = (
            purchased[
                "hist_total_spend"
            ]
            /
            purchased[
                "hist_order_count"
            ]
        )

        actual = (
            purchased[
                "hist_average_order_value"
            ]
        )

        if not np.allclose(
            expected,
            actual,
            rtol=1e-6,
            atol=1e-6,
            equal_nan=True
        ):

            self.errors.append(
                "Historical average order "
                "value does not reconcile."
            )


if __name__ == "__main__":

    print("=" * 70)
    print(
        "PHASE 7 - CUSTOMER FEATURE VALIDATION"
    )
    print("=" * 70)

    validator = (
        CustomerFeatureValidator()
    )

    result = validator.validate()

    print(
        f"\nRows validated: "
        f"{len(validator.features):,}"
    )

    print(
        f"Columns validated: "
        f"{len(validator.features.columns)}"
    )

    print(
        "\nPurchase-history customers "
        "by snapshot:"
    )

    summary = (
        validator.features
        .groupby(
            "snapshot_day"
        )[
            "has_purchase_history"
        ]
        .sum()
    )

    print(summary)

    print(
        "\nValidation result:"
    )

    print(result)

    if not result["passed"]:

        raise AssertionError(
            "Customer feature validation failed."
        )

    print(
        "\nCUSTOMER FEATURE VALIDATION PASSED."
    )