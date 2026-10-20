import json

import numpy as np
import pandas as pd

from src.data_loader import MLDataLoader


class CustomerFeatureBuilder:

    def __init__(self):

        self.loader = MLDataLoader()

        self.config = self.loader.config

        self.customers = (
            self.loader.load_customers()
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
    # CUSTOMER PROFILE FEATURES
    # ======================================================

    def _build_customer_base(
        self,
        snapshot_day
    ):

        safe_columns = [
            "customer_id",
            "segment",
            "price_tendency",
            "discount_sensitivity",
            "premium_product_tendency",
            "repeat_purchase_tendency",
            "city_id",
            "region",
            "acquisition_channel",
            "registration_day"
        ]

        features = (
            self.customers[
                safe_columns
            ]
            .copy()
        )

        features[
            "snapshot_day"
        ] = snapshot_day

        features[
            "customer_tenure_days"
        ] = (
            snapshot_day
            - features[
                "registration_day"
            ]
        )

        features[
            "preferred_category_count"
        ] = (
            self.customers[
                "preferred_categories"
            ]
            .apply(
                self._count_preferred_categories
            )
        )

        return features

    def _count_preferred_categories(
        self,
        value
    ):

        if pd.isna(value):
            return 0

        try:

            parsed = json.loads(
                value
            )

            if isinstance(
                parsed,
                list
            ):
                return len(parsed)

        except (
            json.JSONDecodeError,
            TypeError
        ):
            pass

        return 0

    # ======================================================
    # BEHAVIOR FEATURES
    # ======================================================

    def _aggregate_behavior(
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

        event_counts = (
            dataframe
            .groupby(
                [
                    "customer_id",
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

        activity = (
            dataframe
            .groupby(
                "customer_id"
            )
            .agg(
                active_days=(
                    "simulation_day",
                    "nunique"
                ),

                unique_products=(
                    "product_id",
                    "nunique"
                ),

                unique_categories=(
                    "category",
                    "nunique"
                ),

                last_activity_day=(
                    "simulation_day",
                    "max"
                )
            )
            .rename(
                columns={
                    "active_days":
                        f"{prefix}_active_days",

                    "unique_products":
                        f"{prefix}_unique_products",

                    "unique_categories":
                        f"{prefix}_unique_categories",

                    "last_activity_day":
                        f"{prefix}_last_activity_day"
                }
            )
        )

        result = (
            event_counts
            .join(
                activity,
                how="outer"
            )
            .reset_index()
        )

        return result

    # ======================================================
    # ORDER FEATURES
    # ======================================================

    def _aggregate_orders(
        self,
        dataframe,
        prefix,
        include_recency=False
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
                order_count=(
                    "order_id",
                    "count"
                ),

                total_spend=(
                    "gross_amount",
                    "sum"
                ),

                average_order_value=(
                    "gross_amount",
                    "mean"
                ),

                total_quantity=(
                    "quantity",
                    "sum"
                ),

                unique_products_purchased=(
                    "product_id",
                    "nunique"
                ),

                unique_categories_purchased=(
                    "category",
                    "nunique"
                ),

                last_order_day=(
                    "simulation_day",
                    "max"
                )
            )
            .reset_index()
        )

        rename_map = {
            "order_count":
                f"{prefix}_order_count",

            "total_spend":
                f"{prefix}_total_spend",

            "average_order_value":
                f"{prefix}_average_order_value",

            "total_quantity":
                f"{prefix}_total_quantity",

            "unique_products_purchased":
                f"{prefix}_unique_products_purchased",

            "unique_categories_purchased":
                f"{prefix}_unique_categories_purchased"
        }

        if include_recency:

            rename_map[
                "last_order_day"
            ] = (
                f"{prefix}_last_order_day"
            )

        else:

            aggregation = (
                aggregation.drop(
                    columns=[
                        "last_order_day"
                    ]
                )
            )

        return aggregation.rename(
            columns=rename_map
        )

    # ======================================================
    # ONE SNAPSHOT
    # ======================================================

    def build_snapshot(
        self,
        snapshot_day
    ):

        features = (
            self._build_customer_base(
                snapshot_day
            )
        )

        # ----------------------------------------------
        # HISTORICAL BEHAVIOR
        # ----------------------------------------------

        historical_behavior = (
            self.behavior[
                self.behavior[
                    "simulation_day"
                ]
                <= snapshot_day
            ]
        )

        behavior_all = (
            self._aggregate_behavior(
                historical_behavior,
                "hist"
            )
        )

        features = features.merge(
            behavior_all,
            on="customer_id",
            how="left"
        )

        # ----------------------------------------------
        # 7-DAY BEHAVIOR
        # ----------------------------------------------

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

        behavior_short = (
            self._aggregate_behavior(
                short_behavior,
                "last_7d"
            )
        )

        features = features.merge(
            behavior_short,
            on="customer_id",
            how="left"
        )

        # ----------------------------------------------
        # 30-DAY BEHAVIOR
        # ----------------------------------------------

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

        behavior_long = (
            self._aggregate_behavior(
                long_behavior,
                "last_30d"
            )
        )

        features = features.merge(
            behavior_long,
            on="customer_id",
            how="left"
        )

        # ----------------------------------------------
        # HISTORICAL ORDERS
        # ----------------------------------------------

        historical_orders = (
            self.orders[
                self.orders[
                    "simulation_day"
                ]
                <= snapshot_day
            ]
        )

        orders_all = (
            self._aggregate_orders(
                historical_orders,
                "hist",
                include_recency=True
            )
        )

        features = features.merge(
            orders_all,
            on="customer_id",
            how="left"
        )

        # ----------------------------------------------
        # 7-DAY ORDERS
        # ----------------------------------------------

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

        orders_short = (
            self._aggregate_orders(
                short_orders,
                "last_7d"
            )
        )

        features = features.merge(
            orders_short,
            on="customer_id",
            how="left"
        )

        # ----------------------------------------------
        # 30-DAY ORDERS
        # ----------------------------------------------

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

        orders_long = (
            self._aggregate_orders(
                long_orders,
                "last_30d"
            )
        )

        features = features.merge(
            orders_long,
            on="customer_id",
            how="left"
        )

        # ----------------------------------------------
        # RECENCY
        # ----------------------------------------------

        features[
            "days_since_last_order"
        ] = (
            snapshot_day
            - features[
                "hist_last_order_day"
            ]
        )

        features[
            "days_since_last_activity"
        ] = (
            snapshot_day
            - features[
                "hist_last_activity_day"
            ]
        )

        features[
            "has_purchase_history"
        ] = (
            features[
                "hist_order_count"
            ]
            .fillna(0)
            > 0
        ).astype(int)

        # ----------------------------------------------
        # FUNNEL RATES
        # ----------------------------------------------

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

        # ----------------------------------------------
        # FILL COUNT FEATURES
        # ----------------------------------------------

        count_like_columns = [
            column
            for column in features.columns
            if (
                "_count" in column
                or "_active_days" in column
                or "_unique_" in column
                or "_total_spend" in column
                or "_total_quantity" in column
            )
        ]

        features[
            count_like_columns
        ] = (
            features[
                count_like_columns
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

        feature_tables = []

        for snapshot_day in (
            self.snapshot_days
        ):

            snapshot = (
                self.build_snapshot(
                    snapshot_day
                )
            )

            feature_tables.append(
                snapshot
            )

        return pd.concat(
            feature_tables,
            ignore_index=True
        )


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 70)
    print("PHASE 7 - CUSTOMER FEATURE TABLE TEST")
    print("=" * 70)

    builder = (
        CustomerFeatureBuilder()
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

    print(
        "\nDuplicate "
        "customer/snapshot rows:"
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
        duplicates
    )

    print(
        "\nSample feature columns:"
    )

    print(
        feature_table.columns.tolist()
    )

    print(
        "\nCUSTOMER FEATURE TABLE TEST PASSED."
    )