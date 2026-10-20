import numpy as np
import pandas as pd

from src.data_loader import MLDataLoader


class ConversionFeatureBuilder:

    EVENT_TYPES = [
        "product_view",
        "add_to_cart",
        "purchase_intent",
        "cart_abandonment"
    ]

    def __init__(self):

        self.loader = MLDataLoader()

        self.config = self.loader.config

        self.customers = (
            self.loader.load_customers()
        )

        self.behavior = (
            self.loader.load_ml_behavior_history()
        )

        self.orders = (
            self.loader.load_ml_orders()
        )

        feature_config = self.config[
            "feature_engineering"
        ]

        self.snapshot_days = (
            feature_config[
                "snapshot_days"
            ]
        )

        self.short_window = (
            feature_config[
                "short_window_days"
            ]
        )

        self.long_window = (
            feature_config[
                "long_window_days"
            ]
        )

        self.daily_conversion = (
            self._build_daily_conversion_table()
        )

    # ======================================================
    # SAFE DIVISION
    # ======================================================

    def _safe_divide(
        self,
        numerator,
        denominator
    ):

        return np.where(
            denominator > 0,
            numerator / denominator,
            0.0
        )

    # ======================================================
    # DAILY CONVERSION OPPORTUNITIES
    # ======================================================

    def _build_daily_conversion_table(self):

        # --------------------------------------------------
        # One row per customer/day with behavioral activity
        # --------------------------------------------------

        event_counts = (
            self.behavior
            .groupby(
                [
                    "customer_id",
                    "simulation_day",
                    "event_type"
                ]
            )
            .size()
            .unstack(
                fill_value=0
            )
            .reset_index()
        )

        for event_type in (
            self.EVENT_TYPES
        ):

            if event_type not in (
                event_counts.columns
            ):

                event_counts[
                    event_type
                ] = 0

        for event_type in (
            self.EVENT_TYPES
        ):

            event_counts[
                f"has_{event_type}"
            ] = (
                event_counts[
                    event_type
                ]
                > 0
            ).astype(int)

        daily_behavior = (
            event_counts[
                [
                    "customer_id",
                    "simulation_day",
                    "has_product_view",
                    "has_add_to_cart",
                    "has_purchase_intent",
                    "has_cart_abandonment"
                ]
            ]
            .copy()
        )

        # --------------------------------------------------
        # Actual valid orders by customer/day
        # --------------------------------------------------

        daily_orders = (
            self.orders
            .groupby(
                [
                    "customer_id",
                    "simulation_day"
                ]
            )
            .agg(
                order_count=(
                    "order_id",
                    "count"
                ),

                revenue=(
                    "gross_amount",
                    "sum"
                )
            )
            .reset_index()
        )

        daily_conversion = (
            daily_behavior.merge(
                daily_orders,
                on=[
                    "customer_id",
                    "simulation_day"
                ],
                how="outer"
            )
        )

        behavior_flag_columns = [
            "has_product_view",
            "has_add_to_cart",
            "has_purchase_intent",
            "has_cart_abandonment"
        ]

        daily_conversion[
            behavior_flag_columns
        ] = (
            daily_conversion[
                behavior_flag_columns
            ]
            .fillna(0)
            .astype(int)
        )

        daily_conversion[
            "order_count"
        ] = (
            daily_conversion[
                "order_count"
            ]
            .fillna(0)
            .astype(int)
        )

        daily_conversion[
            "revenue"
        ] = (
            daily_conversion[
                "revenue"
            ]
            .fillna(0.0)
        )

        daily_conversion[
            "converted"
        ] = (
            daily_conversion[
                "order_count"
            ]
            > 0
        ).astype(int)

        # --------------------------------------------------
        # CONVERSION ATTRIBUTION
        #
        # A valid conversion may exist even when the frozen
        # behavior history is missing that customer's funnel
        # events. Only attribute a conversion to a funnel
        # stage when that stage was actually observed.
        # --------------------------------------------------

        daily_conversion[
            "view_converted"
        ] = (
            daily_conversion[
                "converted"
            ]
            *
            daily_conversion[
                "has_product_view"
            ]
        )

        daily_conversion[
            "cart_converted"
        ] = (
            daily_conversion[
                "converted"
            ]
            *
            daily_conversion[
                "has_add_to_cart"
            ]
        )

        daily_conversion[
            "intent_converted"
        ] = (
            daily_conversion[
                "converted"
            ]
            *
            daily_conversion[
                "has_purchase_intent"
            ]
        )

        return daily_conversion

    # ======================================================
    # BASE
    # ======================================================

    def _build_base(
        self,
        snapshot_day
    ):

        features = (
            self.customers[
                [
                    "customer_id"
                ]
            ]
            .copy()
        )

        features[
            "snapshot_day"
        ] = snapshot_day

        return features

    # ======================================================
    # WINDOW AGGREGATION
    # ======================================================

    def _aggregate_window(
        self,
        dataframe,
        prefix
    ):

        if dataframe.empty:

            return pd.DataFrame(
                columns=[
                    "customer_id"
                ]
            )

        aggregation = (
            dataframe
            .groupby(
                "customer_id"
            )
            .agg(
                evaluated_days=(
                    "simulation_day",
                    "nunique"
                ),

                converted_days=(
                    "converted",
                    "sum"
                ),

                order_count=(
                    "order_count",
                    "sum"
                ),

                conversion_revenue=(
                    "revenue",
                    "sum"
                ),

                view_days=(
                    "has_product_view",
                    "sum"
                ),

                cart_days=(
                    "has_add_to_cart",
                    "sum"
                ),

                intent_days=(
                    "has_purchase_intent",
                    "sum"
                ),

                abandonment_days=(
                    "has_cart_abandonment",
                    "sum"
                ),

                view_converted_days=(
                    "view_converted",
                    "sum"
                ),

                cart_converted_days=(
                    "cart_converted",
                    "sum"
                ),

                intent_converted_days=(
                    "intent_converted",
                    "sum"
                ),

                last_evaluation_day=(
                    "simulation_day",
                    "max"
                )
            )
            .reset_index()
        )

        aggregation[
            "nonconverted_days"
        ] = (
            aggregation[
                "evaluated_days"
            ]
            -
            aggregation[
                "converted_days"
            ]
        )

        converted_only = (
            dataframe[
                dataframe[
                    "converted"
                ]
                == 1
            ]
            .groupby(
                "customer_id"
            )[
                "simulation_day"
            ]
            .max()
            .rename(
                "last_conversion_day"
            )
            .reset_index()
        )

        aggregation = (
            aggregation.merge(
                converted_only,
                on="customer_id",
                how="left"
            )
        )

        rename_map = {
            column:
                f"{prefix}_{column}"
            for column in aggregation.columns
            if column != "customer_id"
        }

        return aggregation.rename(
            columns=rename_map
        )

    # ======================================================
    # DERIVED RATES
    # ======================================================

    def _add_window_rates(
        self,
        features,
        prefix
    ):

        evaluated = (
            features[
                f"{prefix}_evaluated_days"
            ]
            .fillna(0)
        )

        converted = (
            features[
                f"{prefix}_converted_days"
            ]
            .fillna(0)
        )

        view_days = (
            features[
                f"{prefix}_view_days"
            ]
            .fillna(0)
        )

        cart_days = (
            features[
                f"{prefix}_cart_days"
            ]
            .fillna(0)
        )

        intent_days = (
            features[
                f"{prefix}_intent_days"
            ]
            .fillna(0)
        )

        view_converted = (
            features[
                f"{prefix}_view_converted_days"
            ]
            .fillna(0)
        )

        cart_converted = (
            features[
                f"{prefix}_cart_converted_days"
            ]
            .fillna(0)
        )

        intent_converted = (
            features[
                f"{prefix}_intent_converted_days"
            ]
            .fillna(0)
        )

        features[
            f"{prefix}_conversion_rate"
        ] = self._safe_divide(
            converted,
            evaluated
        )

        features[
            f"{prefix}_view_to_conversion_rate"
        ] = self._safe_divide(
            view_converted,
            view_days
        )

        features[
            f"{prefix}_cart_to_conversion_rate"
        ] = self._safe_divide(
            cart_converted,
            cart_days
        )

        features[
            f"{prefix}_intent_to_conversion_rate"
        ] = self._safe_divide(
            intent_converted,
            intent_days
        )

        return features

    # ======================================================
    # ONE SNAPSHOT
    # ======================================================

    def build_snapshot(
        self,
        snapshot_day
    ):

        features = (
            self._build_base(
                snapshot_day
            )
        )

        # --------------------------------------------------
        # HISTORICAL
        # --------------------------------------------------

        historical = (
            self.daily_conversion[
                self.daily_conversion[
                    "simulation_day"
                ]
                <= snapshot_day
            ]
        )

        features = features.merge(
            self._aggregate_window(
                historical,
                "hist"
            ),
            on="customer_id",
            how="left"
        )

        # --------------------------------------------------
        # LAST 7 DAYS
        # --------------------------------------------------

        short_start = (
            snapshot_day
            - self.short_window
            + 1
        )

        short_window = (
            self.daily_conversion[
                (
                    self.daily_conversion[
                        "simulation_day"
                    ]
                    >= short_start
                )
                &
                (
                    self.daily_conversion[
                        "simulation_day"
                    ]
                    <= snapshot_day
                )
            ]
        )

        features = features.merge(
            self._aggregate_window(
                short_window,
                "last_7d"
            ),
            on="customer_id",
            how="left"
        )

        # --------------------------------------------------
        # LAST 30 DAYS
        # --------------------------------------------------

        long_start = (
            snapshot_day
            - self.long_window
            + 1
        )

        long_window = (
            self.daily_conversion[
                (
                    self.daily_conversion[
                        "simulation_day"
                    ]
                    >= long_start
                )
                &
                (
                    self.daily_conversion[
                        "simulation_day"
                    ]
                    <= snapshot_day
                )
            ]
        )

        features = features.merge(
            self._aggregate_window(
                long_window,
                "last_30d"
            ),
            on="customer_id",
            how="left"
        )

        # --------------------------------------------------
        # ZERO-FILL COUNTS / REVENUE
        # --------------------------------------------------

        fill_tokens = [
            "_evaluated_days",
            "_converted_days",
            "_nonconverted_days",
            "_order_count",
            "_conversion_revenue",
            "_view_days",
            "_cart_days",
            "_intent_days",
            "_abandonment_days",
            "_view_converted_days",
            "_cart_converted_days",
            "_intent_converted_days"
        ]

        fill_columns = [
            column
            for column
            in features.columns
            if any(
                token in column
                for token in fill_tokens
            )
        ]

        features[
            fill_columns
        ] = (
            features[
                fill_columns
            ]
            .fillna(0)
        )

        # --------------------------------------------------
        # CONVERSION RATES
        # --------------------------------------------------

        for prefix in [
            "hist",
            "last_7d",
            "last_30d"
        ]:

            features = (
                self._add_window_rates(
                    features,
                    prefix
                )
            )

        # --------------------------------------------------
        # RECENCY
        # --------------------------------------------------

        features[
            "days_since_last_evaluation"
        ] = (
            snapshot_day
            -
            features[
                "hist_last_evaluation_day"
            ]
        )

        features[
            "days_since_last_conversion"
        ] = (
            snapshot_day
            -
            features[
                "hist_last_conversion_day"
            ]
        )

        features[
            "has_historical_conversion"
        ] = (
            features[
                "hist_converted_days"
            ]
            > 0
        ).astype(int)

        # --------------------------------------------------
        # RECENT CONVERSION MOMENTUM
        # --------------------------------------------------

        features[
            "conversion_rate_change_7d_vs_30d"
        ] = (
            features[
                "last_7d_conversion_rate"
            ]
            -
            features[
                "last_30d_conversion_rate"
            ]
        )

        features[
            "evaluation_activity_share_7d_of_30d"
        ] = self._safe_divide(
            features[
                "last_7d_evaluated_days"
            ],
            features[
                "last_30d_evaluated_days"
            ]
        )

        features[
            "conversion_activity_share_7d_of_30d"
        ] = self._safe_divide(
            features[
                "last_7d_converted_days"
            ],
            features[
                "last_30d_converted_days"
            ]
        )

        return features

    # ======================================================
    # ALL SNAPSHOTS
    # ======================================================

    def build_all_snapshots(
        self
    ):

        tables = []

        for snapshot_day in (
            self.snapshot_days
        ):

            tables.append(
                self.build_snapshot(
                    snapshot_day
                )
            )

        return pd.concat(
            tables,
            ignore_index=True
        )


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 70)
    print(
        "PHASE 7 - CONVERSION FEATURE TABLE TEST"
    )
    print("=" * 70)

    builder = (
        ConversionFeatureBuilder()
    )

    feature_table = (
        builder.build_all_snapshots()
    )

    print(
        f"\nRows: "
        f"{len(feature_table):,}"
    )

    print(
        f"Columns: "
        f"{len(feature_table.columns)}"
    )

    print(
        "\nRows by snapshot:"
    )

    print(
        feature_table[
            "snapshot_day"
        ]
        .value_counts()
        .sort_index()
    )

    duplicates = (
        feature_table
        .duplicated(
            subset=[
                "customer_id",
                "snapshot_day"
            ]
        )
        .sum()
    )

    print(
        "\nDuplicate customer/snapshot rows:"
    )

    print(duplicates)

    print(
        "\nCustomers with historical conversion:"
    )

    print(
        feature_table
        .groupby(
            "snapshot_day"
        )[
            "has_historical_conversion"
        ]
        .sum()
    )

    print(
        "\nHistorical evaluated days:"
    )

    print(
        feature_table
        .groupby(
            "snapshot_day"
        )[
            "hist_evaluated_days"
        ]
        .sum()
    )

    print(
        "\nHistorical converted days:"
    )

    print(
        feature_table
        .groupby(
            "snapshot_day"
        )[
            "hist_converted_days"
        ]
        .sum()
    )

    print(
        "\nFeature columns:"
    )

    print(
        feature_table.columns.tolist()
    )

    print(
        "\nCONVERSION FEATURE TABLE TEST PASSED."
    )