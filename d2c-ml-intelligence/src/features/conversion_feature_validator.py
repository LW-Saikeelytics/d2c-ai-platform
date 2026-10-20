import numpy as np

from src.features.conversion_features import (
    ConversionFeatureBuilder
)


class ConversionFeatureValidator:

    def __init__(self):

        self.builder = (
            ConversionFeatureBuilder()
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
        self._validate_conversion_accounting()
        self._validate_order_relationship()
        self._validate_conversion_flags()
        self._validate_source_order_reconciliation()
        self._validate_finite_values()

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

    # ======================================================
    # NON-NEGATIVE
    # ======================================================

    def _validate_non_negative_values(self):

        exclude_columns = {
            "conversion_rate_change_7d_vs_30d"
        }

        numeric_columns = (
            self.features
            .select_dtypes(
                include=[
                    "number"
                ]
            )
            .columns
        )

        for column in numeric_columns:

            if column in exclude_columns:
                continue

            values = (
                self.features[
                    column
                ]
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
            column
            for column
            in self.features.columns
            if (
                column.endswith(
                    "_conversion_rate"
                )
                or column in {
                    "evaluation_activity_share_7d_of_30d",
                    "conversion_activity_share_7d_of_30d"
                }
            )
        ]

        for column in rate_columns:

            invalid = (
                (
                    self.features[
                        column
                    ] < 0
                )
                |
                (
                    self.features[
                        column
                    ] > 1
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
            "evaluated_days",
            "converted_days",
            "nonconverted_days",
            "order_count",
            "conversion_revenue",
            "view_days",
            "cart_days",
            "intent_days",
            "abandonment_days",
            "view_converted_days",
            "cart_converted_days",
            "intent_converted_days",
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
            "hist_evaluated_days",
            "hist_converted_days",
            "hist_nonconverted_days",
            "hist_order_count",
            "hist_conversion_revenue",
            "hist_view_days",
            "hist_cart_days",
            "hist_intent_days",
            "hist_abandonment_days",
            "hist_view_converted_days",
            "hist_cart_converted_days",
            "hist_intent_converted_days",
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
                differences < 0
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

        for column in [
            "hist_last_evaluation_day",
            "hist_last_conversion_day"
        ]:

            invalid = (
                self.features[
                    column
                ]
                .notna()
                &
                (
                    self.features[
                        column
                    ]
                    >
                    self.features[
                        "snapshot_day"
                    ]
                )
            )

            if invalid.any():

                self.errors.append(
                    f"{column} contains "
                    "future information."
                )

    # ======================================================
    # CONVERSION ACCOUNTING
    # ======================================================

    def _validate_conversion_accounting(
        self
    ):

        prefixes = [
            "hist",
            "last_7d",
            "last_30d"
        ]

        for prefix in prefixes:

            evaluated = (
                self.features[
                    f"{prefix}_evaluated_days"
                ]
            )

            converted = (
                self.features[
                    f"{prefix}_converted_days"
                ]
            )

            nonconverted = (
                self.features[
                    f"{prefix}_nonconverted_days"
                ]
            )

            if not (
                evaluated
                ==
                converted
                +
                nonconverted
            ).all():

                self.errors.append(
                    f"{prefix} conversion "
                    "day accounting does "
                    "not reconcile."
                )

            if (
                self.features[
                    f"{prefix}_view_converted_days"
                ]
                >
                self.features[
                    f"{prefix}_view_days"
                ]
            ).any():

                self.errors.append(
                    f"{prefix} view-attributed "
                    "conversions exceed view days."
                )

            if (
                self.features[
                    f"{prefix}_cart_converted_days"
                ]
                >
                self.features[
                    f"{prefix}_cart_days"
                ]
            ).any():

                self.errors.append(
                    f"{prefix} cart-attributed "
                    "conversions exceed cart days."
                )

            if (
                self.features[
                    f"{prefix}_intent_converted_days"
                ]
                >
                self.features[
                    f"{prefix}_intent_days"
                ]
            ).any():

                self.errors.append(
                    f"{prefix} intent-attributed "
                    "conversions exceed intent days."
                )

    # ======================================================
    # ORDER RELATIONSHIP
    # ======================================================

    def _validate_order_relationship(
        self
    ):

        prefixes = [
            "hist",
            "last_7d",
            "last_30d"
        ]

        for prefix in prefixes:

            converted_days = (
                self.features[
                    f"{prefix}_converted_days"
                ]
            )

            order_count = (
                self.features[
                    f"{prefix}_order_count"
                ]
            )

            # One converted day may contain
            # one or more orders.
            if (
                converted_days
                >
                order_count
            ).any():

                self.errors.append(
                    f"{prefix} converted days "
                    "exceed order count."
                )

    # ======================================================
    # CONVERSION FLAG
    # ======================================================

    def _validate_conversion_flags(
        self
    ):

        expected = (
            self.features[
                "hist_converted_days"
            ]
            > 0
        ).astype(int)

        actual = (
            self.features[
                "has_historical_conversion"
            ]
        )

        if not (
            expected
            ==
            actual
        ).all():

            self.errors.append(
                "has_historical_conversion "
                "is inconsistent."
            )

    # ======================================================
    # FINITE VALUES
    # ======================================================

    def _validate_finite_values(self):

        derived_columns = [
            column
            for column
            in self.features.columns
            if (
                "_rate" in column
                or "_share_" in column
            )
        ]

        values = (
            self.features[
                derived_columns
            ]
            .to_numpy(
                dtype=float
            )
        )

        if not np.isfinite(
            values
        ).all():

            self.errors.append(
                "NaN or infinite values "
                "found in derived "
                "conversion features."
            )

    # ======================================================
    # SOURCE ORDER RECONCILIATION
    # ======================================================

    def _validate_source_order_reconciliation(
        self
    ):

        source_orders = (
            self.builder.orders
        )

        for snapshot_day in (
            self.builder.snapshot_days
        ):

            source = (
                source_orders[
                    source_orders[
                        "simulation_day"
                    ]
                    <= snapshot_day
                ]
            )

            expected_orders = (
                len(source)
            )

            expected_revenue = (
                source[
                    "gross_amount"
                ]
                .sum()
            )

            snapshot_features = (
                self.features[
                    self.features[
                        "snapshot_day"
                    ]
                    == snapshot_day
                ]
            )

            actual_orders = (
                snapshot_features[
                    "hist_order_count"
                ]
                .sum()
            )

            actual_revenue = (
                snapshot_features[
                    "hist_conversion_revenue"
                ]
                .sum()
            )

            if (
                actual_orders
                != expected_orders
            ):

                self.errors.append(
                    f"Snapshot {snapshot_day}: "
                    "conversion feature order count "
                    f"{actual_orders} does not match "
                    f"source order count "
                    f"{expected_orders}."
                )

            if not np.isclose(
                actual_revenue,
                expected_revenue,
                rtol=1e-6,
                atol=1e-6
            ):

                self.errors.append(
                    f"Snapshot {snapshot_day}: "
                    "conversion feature revenue "
                    f"{actual_revenue} does not match "
                    f"source revenue "
                    f"{expected_revenue}."
                )

if __name__ == "__main__":

    print("=" * 70)
    print(
        "PHASE 7 - CONVERSION FEATURE VALIDATION"
    )
    print("=" * 70)

    validator = (
        ConversionFeatureValidator()
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
        "\nOrders vs converted days:"
    )

    summary = (
        validator.features
        .groupby(
            "snapshot_day"
        )[
            [
                "hist_order_count",
                "hist_converted_days"
            ]
        ]
        .sum()
    )

    print(summary)

    print(
        "\nCustomers with historical conversion:"
    )

    print(
        validator.features
        .groupby(
            "snapshot_day"
        )[
            "has_historical_conversion"
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
            "Conversion feature "
            "validation failed."
        )

    print(
        "\nCONVERSION FEATURE "
        "VALIDATION PASSED."
    )
