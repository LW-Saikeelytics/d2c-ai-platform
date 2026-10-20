import numpy as np
import pandas as pd

from src.data_loader import MLDataLoader


class BehaviorFeatureBuilder:

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

        # Use temporally cleaned ML data,
        # not the untouched raw frozen source.
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
    # BASE TABLE
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
    # AGGREGATION
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

        # ----------------------------------------------
        # EVENT COUNTS
        # ----------------------------------------------

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

        for event_type in (
            self.EVENT_TYPES
        ):

            if event_type not in (
                event_counts.columns
            ):

                event_counts[
                    event_type
                ] = 0

        event_counts = (
            event_counts[
                self.EVENT_TYPES
            ]
            .rename(
                columns={
                    event_type:
                        f"{prefix}_{event_type}_count"
                    for event_type
                    in self.EVENT_TYPES
                }
            )
        )

        # ----------------------------------------------
        # ENGAGEMENT SUMMARY
        # ----------------------------------------------

        engagement = (
            dataframe
            .groupby(
                "customer_id"
            )
            .agg(
                total_events=(
                    "event_id",
                    "count"
                ),

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
                    "total_events":
                        f"{prefix}_total_events",

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

        return (
            event_counts
            .join(
                engagement,
                how="outer"
            )
            .reset_index()
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

        # ----------------------------------------------
        # HISTORICAL BEHAVIOR
        # ----------------------------------------------

        historical = (
            self.behavior[
                self.behavior[
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

        # ----------------------------------------------
        # LAST 7 DAYS
        # ----------------------------------------------

        short_start = (
            snapshot_day
            - self.short_window
            + 1
        )

        short_window = (
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
            self._aggregate_window(
                short_window,
                "last_7d"
            ),
            on="customer_id",
            how="left"
        )

        # ----------------------------------------------
        # LAST 30 DAYS
        # ----------------------------------------------

        long_start = (
            snapshot_day
            - self.long_window
            + 1
        )

        long_window = (
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
            self._aggregate_window(
                long_window,
                "last_30d"
            ),
            on="customer_id",
            how="left"
        )

        # ----------------------------------------------
        # ZERO-FILL COUNTS
        # ----------------------------------------------

        zero_fill_tokens = [
            "_count",
            "_total_events",
            "_active_days",
            "_unique_products",
            "_unique_categories"
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

        # ==================================================
        # DERIVED BEHAVIOR FEATURES
        # ==================================================

        # ----------------------------------------------
        # RECENCY
        # ----------------------------------------------

        features[
            "days_since_last_behavior"
        ] = (
            snapshot_day
            - features[
                "hist_last_activity_day"
            ]
        )

        # ----------------------------------------------
        # HISTORICAL FUNNEL
        # ----------------------------------------------

        hist_views = (
            features[
                "hist_product_view_count"
            ]
        )

        hist_carts = (
            features[
                "hist_add_to_cart_count"
            ]
        )

        hist_intents = (
            features[
                "hist_purchase_intent_count"
            ]
        )

        hist_abandonments = (
            features[
                "hist_cart_abandonment_count"
            ]
        )

        features[
            "hist_view_to_cart_rate"
        ] = self._safe_divide(
            hist_carts,
            hist_views
        )

        features[
            "hist_cart_to_intent_rate"
        ] = self._safe_divide(
            hist_intents,
            hist_carts
        )

        features[
            "hist_cart_abandonment_rate"
        ] = self._safe_divide(
            hist_abandonments,
            hist_carts
        )

        features[
            "hist_intent_per_view_rate"
        ] = self._safe_divide(
            hist_intents,
            hist_views
        )

        # ----------------------------------------------
        # BEHAVIOR INTENSITY
        # ----------------------------------------------

        features[
            "hist_events_per_active_day"
        ] = self._safe_divide(
            features[
                "hist_total_events"
            ],
            features[
                "hist_active_days"
            ]
        )

        features[
            "last_7d_events_per_active_day"
        ] = self._safe_divide(
            features[
                "last_7d_total_events"
            ],
            features[
                "last_7d_active_days"
            ]
        )

        features[
            "last_30d_events_per_active_day"
        ] = self._safe_divide(
            features[
                "last_30d_total_events"
            ],
            features[
                "last_30d_active_days"
            ]
        )

        # ----------------------------------------------
        # RECENT ACTIVITY SHARE
        # ----------------------------------------------

        features[
            "recent_event_share_7d_of_30d"
        ] = self._safe_divide(
            features[
                "last_7d_total_events"
            ],
            features[
                "last_30d_total_events"
            ]
        )

        features[
            "recent_active_day_share_7d_of_30d"
        ] = self._safe_divide(
            features[
                "last_7d_active_days"
            ],
            features[
                "last_30d_active_days"
            ]
        )

        # ----------------------------------------------
        # ACTIVITY MOMENTUM
        #
        # Compare recent daily event rate against
        # the broader 30-day daily event rate.
        # Values > 1 mean recent activity is stronger.
        # ----------------------------------------------

        short_daily_rate = (
            features[
                "last_7d_total_events"
            ]
            / self.short_window
        )

        long_daily_rate = (
            features[
                "last_30d_total_events"
            ]
            / self.long_window
        )

        features[
            "activity_momentum_7d_vs_30d"
        ] = self._safe_divide(
            short_daily_rate,
            long_daily_rate
        )

        # ----------------------------------------------
        # EXPLORATION FEATURES
        # ----------------------------------------------

        features[
            "product_exploration_rate"
        ] = self._safe_divide(
            features[
                "hist_unique_products"
            ],
            hist_views
        )

        features[
            "category_exploration_rate"
        ] = self._safe_divide(
            features[
                "hist_unique_categories"
            ],
            hist_views
        )

        # ----------------------------------------------
        # ACTIVE / INACTIVE FLAG
        # ----------------------------------------------

        features[
            "active_in_last_7d"
        ] = (
            features[
                "last_7d_total_events"
            ]
            > 0
        ).astype(int)

        features[
            "active_in_last_30d"
        ] = (
            features[
                "last_30d_total_events"
            ]
            > 0
        ).astype(int)

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
        "PHASE 7 - BEHAVIOR FEATURE TABLE TEST"
    )
    print("=" * 70)

    builder = (
        BehaviorFeatureBuilder()
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

    print(
        duplicates
    )

    print(
        "\nCustomers active in last 7 days:"
    )

    print(
        feature_table
        .groupby(
            "snapshot_day"
        )[
            "active_in_last_7d"
        ]
        .sum()
    )

    print(
        "\nCustomers active in last 30 days:"
    )

    print(
        feature_table
        .groupby(
            "snapshot_day"
        )[
            "active_in_last_30d"
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
        "\nBEHAVIOR FEATURE TABLE TEST PASSED."
    )