import numpy as np

from src.features.behavior_features import (
    BehaviorFeatureBuilder
)


class BehaviorFeatureValidator:

    def __init__(self):

        self.builder = (
            BehaviorFeatureBuilder()
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
        self._validate_event_accounting()
        self._validate_funnel_consistency()
        self._validate_activity_flags()
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
    # LEAKAGE
    # ======================================================

    def _validate_leakage_columns(self):

        forbidden_columns = {
            "purchase_propensity",
            "behavior_profile",
            "status",
            "lifetime_orders",
            "lifetime_spend",
            "last_order_day",
            "conversion_probability",
            "converted"
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
                "Potential leakage columns "
                f"found: {sorted(leaked)}"
            )

    # ======================================================
    # NON-NEGATIVE
    # ======================================================

    def _validate_non_negative_values(self):

        excluded = {
            "hist_last_activity_day",
            "last_7d_last_activity_day",
            "last_30d_last_activity_day"
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

            if column in excluded:
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

        bounded_columns = [
            "hist_view_to_cart_rate",
            "hist_cart_to_intent_rate",
            "hist_cart_abandonment_rate",
            "hist_intent_per_view_rate",
            "recent_event_share_7d_of_30d",
            "recent_active_day_share_7d_of_30d",
            "product_exploration_rate",
            "category_exploration_rate"
        ]

        for column in bounded_columns:

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
                    f"Invalid bounded rate "
                    f"found in {column}."
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
            "total_events",
            "active_days",
            "unique_products",
            "unique_categories"
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
            "hist_product_view_count",
            "hist_add_to_cart_count",
            "hist_purchase_intent_count",
            "hist_cart_abandonment_count",
            "hist_total_events",
            "hist_active_days",
            "hist_unique_products",
            "hist_unique_categories"
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
    # TEMPORAL CONSISTENCY
    # ======================================================

    def _validate_temporal_consistency(
        self
    ):

        has_activity = (
            self.features[
                "hist_last_activity_day"
            ]
            .notna()
        )

        future_activity = (
            has_activity
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

        if future_activity.any():

            self.errors.append(
                "Historical behavior "
                "contains future activity."
            )

        expected_recency = (
            self.features.loc[
                has_activity,
                "snapshot_day"
            ]
            -
            self.features.loc[
                has_activity,
                "hist_last_activity_day"
            ]
        )

        actual_recency = (
            self.features.loc[
                has_activity,
                "days_since_last_behavior"
            ]
        )

        if not np.allclose(
            expected_recency,
            actual_recency,
            rtol=1e-6,
            atol=1e-6
        ):

            self.errors.append(
                "days_since_last_behavior "
                "does not reconcile."
            )

    # ======================================================
    # EVENT ACCOUNTING
    # ======================================================

    def _validate_event_accounting(self):

        prefixes = [
            "hist",
            "last_7d",
            "last_30d"
        ]

        for prefix in prefixes:

            calculated_total = (
                self.features[
                    f"{prefix}_product_view_count"
                ]
                +
                self.features[
                    f"{prefix}_add_to_cart_count"
                ]
                +
                self.features[
                    f"{prefix}_purchase_intent_count"
                ]
                +
                self.features[
                    f"{prefix}_cart_abandonment_count"
                ]
            )

            actual_total = (
                self.features[
                    f"{prefix}_total_events"
                ]
            )

            if not (
                calculated_total
                ==
                actual_total
            ).all():

                self.errors.append(
                    f"{prefix} event totals "
                    "do not reconcile."
                )

    # ======================================================
    # FUNNEL CONSISTENCY
    # ======================================================

    def _validate_funnel_consistency(self):

        prefixes = [
            "hist",
            "last_7d",
            "last_30d"
        ]

        for prefix in prefixes:

            carts = (
                self.features[
                    f"{prefix}_add_to_cart_count"
                ]
            )

            outcomes = (
                self.features[
                    f"{prefix}_purchase_intent_count"
                ]
                +
                self.features[
                    f"{prefix}_cart_abandonment_count"
                ]
            )

            if not (
                carts
                ==
                outcomes
            ).all():

                self.errors.append(
                    f"{prefix} cart funnel "
                    "does not reconcile: "
                    "add_to_cart != "
                    "purchase_intent + "
                    "cart_abandonment."
                )

    # ======================================================
    # ACTIVITY FLAGS
    # ======================================================

    def _validate_activity_flags(self):

        expected_7d = (
            self.features[
                "last_7d_total_events"
            ]
            > 0
        ).astype(int)

        if not (
            expected_7d
            ==
            self.features[
                "active_in_last_7d"
            ]
        ).all():

            self.errors.append(
                "active_in_last_7d "
                "is inconsistent."
            )

        expected_30d = (
            self.features[
                "last_30d_total_events"
            ]
            > 0
        ).astype(int)

        if not (
            expected_30d
            ==
            self.features[
                "active_in_last_30d"
            ]
        ).all():

            self.errors.append(
                "active_in_last_30d "
                "is inconsistent."
            )

    # ======================================================
    # FINITE VALUES
    # ======================================================

    def _validate_finite_values(self):

        derived_columns = [
            "hist_view_to_cart_rate",
            "hist_cart_to_intent_rate",
            "hist_cart_abandonment_rate",
            "hist_intent_per_view_rate",
            "hist_events_per_active_day",
            "last_7d_events_per_active_day",
            "last_30d_events_per_active_day",
            "recent_event_share_7d_of_30d",
            "recent_active_day_share_7d_of_30d",
            "activity_momentum_7d_vs_30d",
            "product_exploration_rate",
            "category_exploration_rate"
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
                "found in derived behavior features."
            )


if __name__ == "__main__":

    print("=" * 70)
    print(
        "PHASE 7 - BEHAVIOR FEATURE VALIDATION"
    )
    print("=" * 70)

    validator = (
        BehaviorFeatureValidator()
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
        "\nHistorical behavior events "
        "by snapshot:"
    )

    print(
        validator.features
        .groupby(
            "snapshot_day"
        )[
            "hist_total_events"
        ]
        .sum()
    )

    print(
        "\nActive customers "
        "in last 7 days:"
    )

    print(
        validator.features
        .groupby(
            "snapshot_day"
        )[
            "active_in_last_7d"
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
            "Behavior feature "
            "validation failed."
        )

    print(
        "\nBEHAVIOR FEATURE "
        "VALIDATION PASSED."
    )
    