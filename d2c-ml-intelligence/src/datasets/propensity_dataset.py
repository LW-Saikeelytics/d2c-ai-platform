import pandas as pd

from src.data_loader import MLDataLoader

from src.features.customer_features import (
    CustomerFeatureBuilder
)

from src.features.conversion_features import (
    ConversionFeatureBuilder
)


class PropensityDatasetBuilder:

    def __init__(self):

        self.loader = MLDataLoader()

        self.config = self.loader.config

        # --------------------------------------------------
        # CUSTOMER FEATURES
        # --------------------------------------------------

        self.customer_feature_builder = (
            CustomerFeatureBuilder()
        )

        self.customer_features = (
            self.customer_feature_builder
            .build_all_snapshots()
        )

        # --------------------------------------------------
        # CONVERSION FEATURES
        # --------------------------------------------------

        self.conversion_feature_builder = (
            ConversionFeatureBuilder()
        )

        self.conversion_features = (
            self.conversion_feature_builder
            .build_all_snapshots()
        )

        # --------------------------------------------------
        # CLEAN VALID ORDERS
        # --------------------------------------------------

        self.orders = (
            self.loader.load_ml_orders()
        )

        self.snapshot_days = (
            self.config[
                "feature_engineering"
            ][
                "snapshot_days"
            ]
        )

        self.label_window_days = (
            self.config[
                "training_datasets"
            ][
                "purchase_propensity"
            ][
                "label_window_days"
            ]
        )

    # ======================================================
    # FEATURE TABLE
    # ======================================================

    def _build_feature_table(
        self,
        snapshot_day
    ):

        customer_features = (
            self.customer_features[
                self.customer_features[
                    "snapshot_day"
                ]
                == snapshot_day
            ]
            .copy()
        )

        # --------------------------------------------------
        # Only conversion-specific features are added here.
        #
        # We deliberately avoid duplicating order / behavior
        # metrics already present in customer_features.
        # --------------------------------------------------

        conversion_columns = [
            "customer_id",
            "snapshot_day",

            "hist_evaluated_days",
            "hist_converted_days",
            "hist_nonconverted_days",

            "hist_conversion_rate",
            "hist_view_to_conversion_rate",
            "hist_cart_to_conversion_rate",
            "hist_intent_to_conversion_rate",

            "last_7d_conversion_rate",
            "last_30d_conversion_rate",

            "days_since_last_evaluation",
            "days_since_last_conversion",

            "has_historical_conversion",

            "conversion_rate_change_7d_vs_30d",
            "evaluation_activity_share_7d_of_30d",
            "conversion_activity_share_7d_of_30d"
        ]

        conversion_features = (
            self.conversion_features[
                self.conversion_features[
                    "snapshot_day"
                ]
                == snapshot_day
            ][
                conversion_columns
            ]
            .copy()
        )

        features = (
            customer_features.merge(
                conversion_features,
                on=[
                    "customer_id",
                    "snapshot_day"
                ],
                how="left",
                validate="one_to_one"
            )
        )

        return features

    # ======================================================
    # FUTURE PURCHASE LABEL
    # ======================================================

    def _build_future_purchase_labels(
        self,
        snapshot_day
    ):

        future_start = (
            snapshot_day + 1
        )

        future_end = (
            snapshot_day
            + self.label_window_days
        )

        future_orders = (
            self.orders[
                (
                    self.orders[
                        "simulation_day"
                    ]
                    >= future_start
                )
                &
                (
                    self.orders[
                        "simulation_day"
                    ]
                    <= future_end
                )
            ]
        )

        labels = (
            future_orders
            .groupby(
                "customer_id"
            )
            .agg(
                future_order_count=(
                    "order_id",
                    "count"
                )
            )
            .reset_index()
        )

        labels[
            "purchase_propensity_label"
        ] = (
            labels[
                "future_order_count"
            ]
            > 0
        ).astype(int)

        return labels

    # ======================================================
    # ONE SNAPSHOT
    # ======================================================

    def build_snapshot(
        self,
        snapshot_day
    ):

        dataset = (
            self._build_feature_table(
                snapshot_day
            )
        )

        labels = (
            self._build_future_purchase_labels(
                snapshot_day
            )
        )

        dataset = (
            dataset.merge(
                labels,
                on="customer_id",
                how="left",
                validate="one_to_one"
            )
        )

        dataset[
            "future_order_count"
        ] = (
            dataset[
                "future_order_count"
            ]
            .fillna(0)
        )

        dataset[
            "purchase_propensity_label"
        ] = (
            dataset[
                "purchase_propensity_label"
            ]
            .fillna(0)
            .astype(int)
        )

        # --------------------------------------------------
        # IMPORTANT:
        # future_order_count is target-construction data.
        # It must never become an ML feature.
        # --------------------------------------------------

        dataset = (
            dataset.drop(
                columns=[
                    "future_order_count"
                ]
            )
        )

        return dataset

    # ======================================================
    # ALL SNAPSHOTS
    # ======================================================

    def build_dataset(self):

        datasets = []

        for snapshot_day in (
            self.snapshot_days
        ):

            datasets.append(
                self.build_snapshot(
                    snapshot_day
                )
            )

        return pd.concat(
            datasets,
            ignore_index=True
        )


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 70)

    print(
        "PHASE 7 - PURCHASE PROPENSITY "
        "DATASET TEST"
    )

    print("=" * 70)

    builder = (
        PropensityDatasetBuilder()
    )

    dataset = (
        builder.build_dataset()
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
        "\nRows by snapshot:"
    )

    print(
        dataset[
            "snapshot_day"
        ]
        .value_counts()
        .sort_index()
    )

    print(
        "\nTarget distribution:"
    )

    print(
        dataset[
            "purchase_propensity_label"
        ]
        .value_counts()
        .sort_index()
    )

    print(
        "\nTarget distribution by snapshot:"
    )

    print(
        pd.crosstab(
            dataset[
                "snapshot_day"
            ],
            dataset[
                "purchase_propensity_label"
            ]
        )
    )

    print(
        "\nPurchase rate by snapshot:"
    )

    print(
        dataset
        .groupby(
            "snapshot_day"
        )[
            "purchase_propensity_label"
        ]
        .mean()
    )

    duplicates = (
        dataset
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
        "\nTarget dtype:"
    )

    print(
        dataset[
            "purchase_propensity_label"
        ]
        .dtype
    )

    print(
        "\nPURCHASE PROPENSITY "
        "DATASET TEST PASSED."
    )
    