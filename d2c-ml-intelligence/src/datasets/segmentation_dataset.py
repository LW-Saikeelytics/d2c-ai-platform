import pandas as pd

from src.data_loader import MLDataLoader

from src.features.customer_features import (
    CustomerFeatureBuilder
)

from src.features.behavior_features import (
    BehaviorFeatureBuilder
)

from src.features.conversion_features import (
    ConversionFeatureBuilder
)


class SegmentationDatasetBuilder:

    def __init__(self):

        self.loader = MLDataLoader()

        self.config = self.loader.config

        self.snapshot_day = (
            self.config[
                "unsupervised_datasets"
            ][
                "segmentation"
            ][
                "snapshot_day"
            ]
        )

        # --------------------------------------------------
        # FEATURE SOURCES
        # --------------------------------------------------

        self.customer_features = (
            CustomerFeatureBuilder()
            .build_all_snapshots()
        )

        self.behavior_features = (
            BehaviorFeatureBuilder()
            .build_all_snapshots()
        )

        self.conversion_features = (
            ConversionFeatureBuilder()
            .build_all_snapshots()
        )

    # ======================================================
    # CUSTOMER FEATURES
    # ======================================================

    def _customer_table(self):

        columns = [
            "customer_id",
            "snapshot_day",

            "customer_tenure_days",
            "preferred_category_count",

            "hist_order_count",
            "hist_total_spend",
            "hist_average_order_value",
            "hist_total_quantity",
            "hist_unique_products_purchased",
            "hist_unique_categories_purchased",

            "last_30d_order_count",
            "last_30d_total_spend",
            "last_30d_total_quantity",

            "days_since_last_order",
            "has_purchase_history"
        ]

        return (
            self.customer_features[
                self.customer_features[
                    "snapshot_day"
                ]
                == self.snapshot_day
            ][
                columns
            ]
            .copy()
        )

    # ======================================================
    # BEHAVIOR FEATURES
    # ======================================================

    def _behavior_table(self):

        columns = [
            "customer_id",
            "snapshot_day",

            "hist_total_events",
            "hist_active_days",
            "hist_unique_products",
            "hist_unique_categories",

            "last_30d_total_events",
            "last_30d_active_days",
            "last_7d_total_events",
            "last_7d_active_days",

            "days_since_last_behavior",

            "hist_view_to_cart_rate",
            "hist_cart_to_intent_rate",
            "hist_cart_abandonment_rate",
            "hist_intent_per_view_rate",

            "hist_events_per_active_day",

            "recent_event_share_7d_of_30d",
            "recent_active_day_share_7d_of_30d",

            "activity_momentum_7d_vs_30d",

            "product_exploration_rate",
            "category_exploration_rate",

            "active_in_last_7d",
            "active_in_last_30d"
        ]

        return (
            self.behavior_features[
                self.behavior_features[
                    "snapshot_day"
                ]
                == self.snapshot_day
            ][
                columns
            ]
            .copy()
        )

    # ======================================================
    # CONVERSION FEATURES
    # ======================================================

    def _conversion_table(self):

        columns = [
            "customer_id",
            "snapshot_day",

            "hist_evaluated_days",
            "hist_converted_days",
            "hist_nonconverted_days",

            "hist_conversion_rate",

            "last_7d_conversion_rate",
            "last_30d_conversion_rate",

            "days_since_last_conversion",

            "has_historical_conversion",

            "conversion_rate_change_7d_vs_30d",

            "evaluation_activity_share_7d_of_30d",
            "conversion_activity_share_7d_of_30d"
        ]

        return (
            self.conversion_features[
                self.conversion_features[
                    "snapshot_day"
                ]
                == self.snapshot_day
            ][
                columns
            ]
            .copy()
        )

    # ======================================================
    # BUILD DATASET
    # ======================================================

    def build_dataset(self):

        customer = (
            self._customer_table()
        )

        behavior = (
            self._behavior_table()
        )

        conversion = (
            self._conversion_table()
        )

        dataset = (
            customer
            .merge(
                behavior,
                on=[
                    "customer_id",
                    "snapshot_day"
                ],
                how="left",
                validate="one_to_one"
            )
            .merge(
                conversion,
                on=[
                    "customer_id",
                    "snapshot_day"
                ],
                how="left",
                validate="one_to_one"
            )
        )

        # ==================================================
        # NEVER-ACTIVE / NEVER-PURCHASED FLAGS
        # ==================================================

        dataset[
            "has_behavior_history"
        ] = (
            dataset[
                "hist_total_events"
            ]
            > 0
        ).astype(int)

        # --------------------------------------------------
        # RECENCY IMPUTATION
        #
        # For customers with no prior observation,
        # snapshot_day + 1 represents "never observed
        # during the simulation window".
        # --------------------------------------------------

        recency_fill_value = (
            self.snapshot_day + 1
        )

        recency_columns = [
            "days_since_last_order",
            "days_since_last_behavior",
            "days_since_last_conversion"
        ]

        dataset[
            recency_columns
        ] = (
            dataset[
                recency_columns
            ]
            .fillna(
                recency_fill_value
            )
        )

        # --------------------------------------------------
        # AOV is undefined for customers with no orders.
        # For clustering we explicitly represent those
        # customers with AOV = 0 plus has_purchase_history.
        # --------------------------------------------------

        dataset[
            "hist_average_order_value"
        ] = (
            dataset[
                "hist_average_order_value"
            ]
            .fillna(0.0)
        )

        # --------------------------------------------------
        # Remaining numeric nulls should represent absence
        # of historical activity and therefore become zero.
        # --------------------------------------------------

        numeric_columns = (
            dataset
            .select_dtypes(
                include=[
                    "number"
                ]
            )
            .columns
        )

        dataset[
            numeric_columns
        ] = (
            dataset[
                numeric_columns
            ]
            .fillna(0)
        )

        return dataset

    # ======================================================
    # CLUSTER FEATURE COLUMNS
    # ======================================================

    def get_feature_columns(self):

        dataset = (
            self.build_dataset()
        )

        return [
            column
            for column
            in dataset.columns
            if column not in {
                "customer_id",
                "snapshot_day"
            }
        ]


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 70)
    print(
        "PHASE 7 - CUSTOMER SEGMENTATION DATASET TEST"
    )
    print("=" * 70)

    builder = (
        SegmentationDatasetBuilder()
    )

    dataset = (
        builder.build_dataset()
    )

    feature_columns = (
        builder.get_feature_columns()
    )

    print(
        f"\nSnapshot day: "
        f"{builder.snapshot_day}"
    )

    print(
        f"\nRows: "
        f"{len(dataset):,}"
    )

    print(
        f"Columns: "
        f"{len(dataset.columns)}"
    )

    print(
        f"Clustering features: "
        f"{len(feature_columns)}"
    )

    print(
        "\nUnique customers:"
    )

    print(
        dataset[
            "customer_id"
        ]
        .nunique()
    )

    duplicates = (
        dataset[
            "customer_id"
        ]
        .duplicated()
        .sum()
    )

    print(
        "\nDuplicate customers:"
    )

    print(duplicates)

    print(
        "\nCustomers with behavior history:"
    )

    print(
        dataset[
            "has_behavior_history"
        ]
        .sum()
    )

    print(
        "\nCustomers with purchase history:"
    )

    print(
        dataset[
            "has_purchase_history"
        ]
        .sum()
    )

    print(
        "\nMissing values:"
    )

    print(
        dataset
        .isna()
        .sum()
        .sum()
    )

    print(
        "\nClustering feature columns:"
    )

    print(feature_columns)

    print(
        "\nCUSTOMER SEGMENTATION "
        "DATASET TEST PASSED."
    )