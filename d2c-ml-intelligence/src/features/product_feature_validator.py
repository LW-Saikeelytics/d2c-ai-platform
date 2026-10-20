import numpy as np

from src.features.product_features import (
    ProductFeatureBuilder
)


class ProductFeatureValidator:

    def __init__(self):

        self.builder = (
            ProductFeatureBuilder()
        )

        self.features = (
            self.builder
            .build_all_snapshots()
        )

        self.errors = []

    def validate(self):

        self._validate_structure()
        self._validate_non_negative_values()
        self._validate_rates()
        self._validate_window_hierarchy()
        self._validate_historical_monotonicity()
        self._validate_temporal_consistency()
        self._validate_launch_consistency()
        self._validate_units_per_order()
        self._validate_revenue_per_buyer()
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
                self.builder.products
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
                    "product_id",
                    "snapshot_day"
                ]
            )
            .sum()
        )

        if duplicates > 0:

            self.errors.append(
                f"Found {duplicates} duplicate "
                "product/snapshot rows."
            )

        expected_per_snapshot = (
            len(
                self.builder.products
            )
        )

        snapshot_counts = (
            self.features[
                "snapshot_day"
            ]
            .value_counts()
            .to_dict()
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
                    f"expected {expected_per_snapshot} "
                    f"products, found {actual}."
                )

    # ======================================================
    # NON-NEGATIVE VALUES
    # ======================================================

    def _validate_non_negative_values(self):

        numeric_tokens = [
            "_count",
            "_customers",
            "_active_days",
            "_order_count",
            "_units_sold",
            "_revenue",
            "_buyers",
            "product_age_days",
            "days_since_last_product"
        ]

        columns = [
            column
            for column in self.features.columns
            if any(
                token in column
                for token in numeric_tokens
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
    # RATES
    # ======================================================

    def _validate_rates(self):

        rate_columns = [
            "view_to_cart_rate",
            "cart_to_intent_rate",
            "cart_abandonment_rate",
            "view_to_order_rate"
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
                    f"Invalid rate found "
                    f"in {column}."
                )

    # ======================================================
    # WINDOW HIERARCHY
    # ======================================================

    def _validate_window_hierarchy(self):

        metrics = [
            "product_view_count",
            "add_to_cart_count",
            "purchase_intent_count",
            "cart_abandonment_count",
            "unique_customers",
            "active_days",
            "order_count",
            "units_sold",
            "revenue",
            "unique_buyers"
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
                column in self.features.columns
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
    # HISTORICAL MONOTONICITY
    # ======================================================

    def _validate_historical_monotonicity(
        self
    ):

        cumulative_columns = [
            "hist_product_view_count",
            "hist_add_to_cart_count",
            "hist_purchase_intent_count",
            "hist_cart_abandonment_count",
            "hist_unique_customers",
            "hist_active_days",
            "hist_order_count",
            "hist_units_sold",
            "hist_revenue",
            "hist_unique_buyers"
        ]

        ordered = (
            self.features
            .sort_values(
                [
                    "product_id",
                    "snapshot_day"
                ]
            )
        )

        for column in cumulative_columns:

            differences = (
                ordered
                .groupby(
                    "product_id"
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
    # TEMPORAL CONSISTENCY
    # ======================================================

    def _validate_temporal_consistency(
        self
    ):

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
                "Historical product activity "
                "contains future activity."
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
                "Historical product orders "
                "contain future orders."
            )

    # ======================================================
    # PRODUCT LAUNCH CONSISTENCY
    # ======================================================

    def _validate_launch_consistency(self):

        product_launch = dict(
            zip(
                self.builder.products[
                    "product_id"
                ],
                self.builder.products[
                    "launch_day"
                ]
            )
        )

        behavior = (
            self.builder.behavior
        )

        behavior_launch_day = (
            behavior[
                "product_id"
            ]
            .map(
                product_launch
            )
        )

        invalid_behavior = (
            behavior[
                "simulation_day"
            ]
            <
            behavior_launch_day
        )

        if invalid_behavior.any():

            self.errors.append(
                "Behavior events found "
                "before product launch."
            )

        orders = (
            self.builder.orders
        )

        order_launch_day = (
            orders[
                "product_id"
            ]
            .map(
                product_launch
            )
        )

        invalid_orders = (
            orders[
                "simulation_day"
            ]
            <
            order_launch_day
        )

        if invalid_orders.any():

            self.errors.append(
                "Orders found before "
                "product launch."
            )

    # ======================================================
    # UNITS PER ORDER
    # ======================================================

    def _validate_units_per_order(self):

        ordered = (
            self.features[
                self.features[
                    "hist_order_count"
                ]
                > 0
            ]
        )

        expected = (
            ordered[
                "hist_units_sold"
            ]
            /
            ordered[
                "hist_order_count"
            ]
        )

        actual = (
            ordered[
                "units_per_order"
            ]
        )

        if not np.allclose(
            expected,
            actual,
            rtol=1e-6,
            atol=1e-6
        ):

            self.errors.append(
                "units_per_order does "
                "not reconcile."
            )

    # ======================================================
    # REVENUE PER BUYER
    # ======================================================

    def _validate_revenue_per_buyer(self):

        purchased = (
            self.features[
                self.features[
                    "hist_unique_buyers"
                ]
                > 0
            ]
        )

        expected = (
            purchased[
                "hist_revenue"
            ]
            /
            purchased[
                "hist_unique_buyers"
            ]
        )

        actual = (
            purchased[
                "revenue_per_buyer"
            ]
        )

        if not np.allclose(
            expected,
            actual,
            rtol=1e-6,
            atol=1e-6
        ):

            self.errors.append(
                "revenue_per_buyer "
                "does not reconcile."
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
                "hist_revenue"
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
            atol=1e-6
        ):

            self.errors.append(
                "Historical average "
                "order value does "
                "not reconcile."
            )


if __name__ == "__main__":

    print("=" * 70)
    print(
        "PHASE 7 - PRODUCT FEATURE VALIDATION"
    )
    print("=" * 70)

    validator = (
        ProductFeatureValidator()
    )

    result = (
        validator.validate()
    )

    print(
        f"\nRows validated: "
        f"{len(validator.features):,}"
    )

    print(
        f"Columns validated: "
        f"{len(validator.features.columns)}"
    )

    print(
        "\nHistorical orders "
        "by snapshot:"
    )

    summary = (
        validator.features
        .groupby(
            "snapshot_day"
        )[
            "hist_order_count"
        ]
        .sum()
    )

    print(summary)

    print(
        "\nHistorical revenue "
        "by snapshot:"
    )

    revenue_summary = (
        validator.features
        .groupby(
            "snapshot_day"
        )[
            "hist_revenue"
        ]
        .sum()
    )

    print(
        revenue_summary
    )

    print(
        "\nValidation result:"
    )

    print(result)

    if not result[
        "passed"
    ]:

        raise AssertionError(
            "Product feature "
            "validation failed."
        )

    print(
        "\nPRODUCT FEATURE "
        "VALIDATION PASSED."
    )