import pandas as pd

from src.data_loader import MLDataLoader

from src.features.customer_features import (
    CustomerFeatureBuilder
)

from src.features.conversion_features import (
    ConversionFeatureBuilder
)


class CLVDatasetBuilder:

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
                "clv"
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

        conversion_columns = [
            "customer_id",
            "snapshot_day",

            "hist_evaluated_days",
            "hist_converted_days",
            "hist_nonconverted_days",

            "hist_conversion_rate",

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

        return (
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

    # ======================================================
    # FUTURE VALUE TARGETS
    # ======================================================

    def _build_future_value(
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

        future_value = (
            future_orders
            .groupby(
                "customer_id"
            )
            .agg(
                future_order_count=(
                    "order_id",
                    "count"
                ),

                future_customer_value_30d=(
                    "gross_amount",
                    "sum"
                )
            )
            .reset_index()
        )

        return future_value

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

        future_value = (
            self._build_future_value(
                snapshot_day
            )
        )

        dataset = (
            dataset.merge(
                future_value,
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
            "future_customer_value_30d"
        ] = (
            dataset[
                "future_customer_value_30d"
            ]
            .fillna(0.0)
        )

        # future_order_count also belongs to the future
        # target window, so do not retain it as a feature.
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
        "PHASE 7 - CLV DATASET TEST"
    )
    print("=" * 70)

    builder = (
        CLVDatasetBuilder()
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
        "\nCustomers with positive future value:"
    )

    print(
        dataset
        .assign(
            future_value_positive=(
                dataset[
                    "future_customer_value_30d"
                ]
                > 0
            ).astype(int)
        )
        .groupby(
            "snapshot_day"
        )[
            "future_value_positive"
        ]
        .sum()
    )

    print(
        "\nTotal future customer value:"
    )

    print(
        dataset
        .groupby(
            "snapshot_day"
        )[
            "future_customer_value_30d"
        ]
        .sum()
    )

    print(
        "\nMean future customer value:"
    )

    print(
        dataset
        .groupby(
            "snapshot_day"
        )[
            "future_customer_value_30d"
        ]
        .mean()
    )

    positive = (
        dataset[
            dataset[
                "future_customer_value_30d"
            ]
            > 0
        ]
    )

    print(
        "\nMean value among purchasing customers:"
    )

    print(
        positive
        .groupby(
            "snapshot_day"
        )[
            "future_customer_value_30d"
        ]
        .mean()
    )

    print(
        "\nMaximum future customer value:"
    )

    print(
        dataset
        .groupby(
            "snapshot_day"
        )[
            "future_customer_value_30d"
        ]
        .max()
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

    print(duplicates)

    print(
        "\nCLV DATASET TEST PASSED."
    )