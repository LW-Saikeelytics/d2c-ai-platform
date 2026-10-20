import numpy as np
import pandas as pd

from src.data_loader import MLDataLoader


class ProductFeatureBuilder:

    def __init__(self):

        self.loader = MLDataLoader()

        self.config = self.loader.config

        self.products = (
            self.loader.load_product_master()
        )

        self.orders = (
            self.loader.load_ml_orders()
        )

        self.behavior = (
            self.loader.load_ml_behavior_history()
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

    # ======================================================
    # PRODUCT BASE
    # ======================================================

    def _build_product_base(
        self,
        snapshot_day
    ):

        safe_columns = [
            "product_id",
            "product_name",
            "category",
            "subcategory",
            "product_type",
            "price_band",
            "positioning",
            "launch_day"
        ]

        features = (
            self.products[
                safe_columns
            ]
            .copy()
        )

        features[
            "snapshot_day"
        ] = snapshot_day

        features[
            "product_age_days"
        ] = (
            snapshot_day
            - features[
                "launch_day"
            ]
        ).clip(lower=0)

        features[
            "is_launched"
        ] = (
            features[
                "launch_day"
            ]
            <= snapshot_day
        ).astype(int)

        return features

    # ======================================================
    # BEHAVIOR AGGREGATION
    # ======================================================

    def _aggregate_behavior(
        self,
        dataframe,
        prefix
    ):

        if dataframe.empty:

            return pd.DataFrame(
                columns=[
                    "product_id"
                ]
            )

        event_counts = (
            dataframe
            .groupby(
                [
                    "product_id",
                    "event_type"
                ]
            )
            .size()
            .unstack(
                fill_value=0
            )
        )

        expected_events = [
            "product_view",
            "add_to_cart",
            "purchase_intent",
            "cart_abandonment"
        ]

        for event_type in expected_events:

            if event_type not in (
                event_counts.columns
            ):

                event_counts[
                    event_type
                ] = 0

        event_counts = (
            event_counts[
                expected_events
            ]
            .rename(
                columns={
                    event_type:
                        f"{prefix}_{event_type}_count"
                    for event_type
                    in expected_events
                }
            )
        )

        engagement = (
            dataframe
            .groupby(
                "product_id"
            )
            .agg(
                unique_customers=(
                    "customer_id",
                    "nunique"
                ),

                active_days=(
                    "simulation_day",
                    "nunique"
                ),

                last_activity_day=(
                    "simulation_day",
                    "max"
                )
            )
            .rename(
                columns={
                    "unique_customers":
                        f"{prefix}_unique_customers",

                    "active_days":
                        f"{prefix}_active_days",

                    "last_activity_day":
                        f"{prefix}_last_activity_day"
                }
            )
        )

        return (
            event_counts
            .join(
                engagement,
                how="outer"
            )
            .reset_index()
        )

    # ======================================================
    # ORDER AGGREGATION
    # ======================================================

    def _aggregate_orders(
        self,
        dataframe,
        prefix
    ):

        if dataframe.empty:

            return pd.DataFrame(
                columns=[
                    "product_id"
                ]
            )

        aggregation = (
            dataframe
            .groupby(
                "product_id"
            )
            .agg(
                order_count=(
                    "order_id",
                    "count"
                ),

                units_sold=(
                    "quantity",
                    "sum"
                ),

                revenue=(
                    "gross_amount",
                    "sum"
                ),

                average_order_value=(
                    "gross_amount",
                    "mean"
                ),

                average_unit_price=(
                    "unit_price",
                    "mean"
                ),

                unique_buyers=(
                    "customer_id",
                    "nunique"
                ),

                last_order_day=(
                    "simulation_day",
                    "max"
                )
            )
            .reset_index()
        )

        return aggregation.rename(
            columns={
                "order_count":
                    f"{prefix}_order_count",

                "units_sold":
                    f"{prefix}_units_sold",

                "revenue":
                    f"{prefix}_revenue",

                "average_order_value":
                    f"{prefix}_average_order_value",

                "average_unit_price":
                    f"{prefix}_average_unit_price",

                "unique_buyers":
                    f"{prefix}_unique_buyers",

                "last_order_day":
                    f"{prefix}_last_order_day"
            }
        )

    # ======================================================
    # SNAPSHOT
    # ======================================================

    def build_snapshot(
        self,
        snapshot_day
    ):

        features = (
            self._build_product_base(
                snapshot_day
            )
        )

        # --------------------------------------------------
        # HISTORICAL BEHAVIOR
        # --------------------------------------------------

        historical_behavior = (
            self.behavior[
                self.behavior[
                    "simulation_day"
                ]
                <= snapshot_day
            ]
        )

        features = features.merge(
            self._aggregate_behavior(
                historical_behavior,
                "hist"
            ),
            on="product_id",
            how="left"
        )

        # --------------------------------------------------
        # 7-DAY BEHAVIOR
        # --------------------------------------------------

        short_start = (
            snapshot_day
            - self.short_window
            + 1
        )

        short_behavior = (
            self.behavior[
                (
                    self.behavior[
                        "simulation_day"
                    ]
                    >= short_start
                )
                &
                (
                    self.behavior[
                        "simulation_day"
                    ]
                    <= snapshot_day
                )
            ]
        )

        features = features.merge(
            self._aggregate_behavior(
                short_behavior,
                "last_7d"
            ),
            on="product_id",
            how="left"
        )

        # --------------------------------------------------
        # 30-DAY BEHAVIOR
        # --------------------------------------------------

        long_start = (
            snapshot_day
            - self.long_window
            + 1
        )

        long_behavior = (
            self.behavior[
                (
                    self.behavior[
                        "simulation_day"
                    ]
                    >= long_start
                )
                &
                (
                    self.behavior[
                        "simulation_day"
                    ]
                    <= snapshot_day
                )
            ]
        )

        features = features.merge(
            self._aggregate_behavior(
                long_behavior,
                "last_30d"
            ),
            on="product_id",
            how="left"
        )

        # --------------------------------------------------
        # HISTORICAL ORDERS
        # --------------------------------------------------

        historical_orders = (
            self.orders[
                self.orders[
                    "simulation_day"
                ]
                <= snapshot_day
            ]
        )

        features = features.merge(
            self._aggregate_orders(
                historical_orders,
                "hist"
            ),
            on="product_id",
            how="left"
        )

        # --------------------------------------------------
        # 7-DAY ORDERS
        # --------------------------------------------------

        short_orders = (
            self.orders[
                (
                    self.orders[
                        "simulation_day"
                    ]
                    >= short_start
                )
                &
                (
                    self.orders[
                        "simulation_day"
                    ]
                    <= snapshot_day
                )
            ]
        )

        features = features.merge(
            self._aggregate_orders(
                short_orders,
                "last_7d"
            ),
            on="product_id",
            how="left"
        )

        # --------------------------------------------------
        # 30-DAY ORDERS
        # --------------------------------------------------

        long_orders = (
            self.orders[
                (
                    self.orders[
                        "simulation_day"
                    ]
                    >= long_start
                )
                &
                (
                    self.orders[
                        "simulation_day"
                    ]
                    <= snapshot_day
                )
            ]
        )

        features = features.merge(
            self._aggregate_orders(
                long_orders,
                "last_30d"
            ),
            on="product_id",
            how="left"
        )

        # --------------------------------------------------
        # RECENCY
        # --------------------------------------------------

        features[
            "days_since_last_product_activity"
        ] = (
            snapshot_day
            - features[
                "hist_last_activity_day"
            ]
        )

        features[
            "days_since_last_product_order"
        ] = (
            snapshot_day
            - features[
                "hist_last_order_day"
            ]
        )

        # --------------------------------------------------
        # FUNNEL FEATURES
        # --------------------------------------------------

        views = (
            features[
                "hist_product_view_count"
            ]
            .fillna(0)
        )

        carts = (
            features[
                "hist_add_to_cart_count"
            ]
            .fillna(0)
        )

        intents = (
            features[
                "hist_purchase_intent_count"
            ]
            .fillna(0)
        )

        abandonments = (
            features[
                "hist_cart_abandonment_count"
            ]
            .fillna(0)
        )

        orders = (
            features[
                "hist_order_count"
            ]
            .fillna(0)
        )

        features[
            "view_to_cart_rate"
        ] = np.where(
            views > 0,
            carts / views,
            0.0
        )

        features[
            "cart_to_intent_rate"
        ] = np.where(
            carts > 0,
            intents / carts,
            0.0
        )

        features[
            "cart_abandonment_rate"
        ] = np.where(
            carts > 0,
            abandonments / carts,
            0.0
        )

        features[
            "view_to_order_rate"
        ] = np.where(
            views > 0,
            orders / views,
            0.0
        )

        # --------------------------------------------------
        # COMMERCIAL FEATURES
        # --------------------------------------------------

        features[
            "units_per_order"
        ] = np.where(
            orders > 0,
            (
                features[
                    "hist_units_sold"
                ]
                .fillna(0)
                / orders
            ),
            0.0
        )

        unique_buyers = (
            features[
                "hist_unique_buyers"
            ]
            .fillna(0)
        )

        features[
            "revenue_per_buyer"
        ] = np.where(
            unique_buyers > 0,
            (
                features[
                    "hist_revenue"
                ]
                .fillna(0)
                / unique_buyers
            ),
            0.0
        )

        # --------------------------------------------------
        # ZERO-FILL NUMERIC AGGREGATES
        # --------------------------------------------------

        zero_fill_tokens = [
            "_count",
            "_unique_customers",
            "_active_days",
            "_order_count",
            "_units_sold",
            "_revenue",
            "_unique_buyers"
        ]

        zero_fill_columns = [
            column
            for column
            in features.columns
            if any(
                token in column
                for token in zero_fill_tokens
            )
        ]

        features[
            zero_fill_columns
        ] = (
            features[
                zero_fill_columns
            ]
            .fillna(0)
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


if __name__ == "__main__":

    print("=" * 70)
    print("PHASE 7 - PRODUCT FEATURE TABLE TEST")
    print("=" * 70)

    builder = (
        ProductFeatureBuilder()
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
                "product_id",
                "snapshot_day"
            ]
        )
        .sum()
    )

    print(
        "\nDuplicate product/snapshot rows:"
    )

    print(
        duplicates
    )

    print(
        "\nProducts represented:"
    )

    print(
        feature_table[
            "product_id"
        ]
        .nunique()
    )

    print(
        "\nFeature columns:"
    )

    print(
        feature_table.columns.tolist()
    )

    print(
        "\nPRODUCT FEATURE TABLE TEST PASSED."
    )