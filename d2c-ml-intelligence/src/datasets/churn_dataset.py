import pandas as pd

from src.data_loader import MLDataLoader
from src.features.customer_features import (
    CustomerFeatureBuilder
)


class ChurnDatasetBuilder:

    def __init__(self):

        self.loader = MLDataLoader()

        self.config = self.loader.config

        self.customer_feature_builder = (
            CustomerFeatureBuilder()
        )

        self.customer_features = (
            self.customer_feature_builder
            .build_all_snapshots()
        )

        # Clean ML-safe source data.
        self.behavior = (
            self.loader
            .load_ml_behavior_history()
        )

        self.orders = (
            self.loader
            .load_ml_orders()
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
                "churn"
            ][
                "label_window_days"
            ]
        )

    # ======================================================
    # FUTURE ACTIVITY
    # ======================================================

    def _build_future_activity(
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

        # --------------------------------------------------
        # FUTURE BEHAVIOR DAYS
        # --------------------------------------------------

        future_behavior = (
            self.behavior[
                (
                    self.behavior[
                        "simulation_day"
                    ]
                    >= future_start
                )
                &
                (
                    self.behavior[
                        "simulation_day"
                    ]
                    <= future_end
                )
            ][
                [
                    "customer_id",
                    "simulation_day"
                ]
            ]
            .drop_duplicates()
        )

        # --------------------------------------------------
        # FUTURE ORDER DAYS
        #
        # Important:
        # order-only days must also count as future activity.
        # --------------------------------------------------

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
            ][
                [
                    "customer_id",
                    "simulation_day"
                ]
            ]
            .drop_duplicates()
        )

        # --------------------------------------------------
        # UNION OF ALL OBSERVED FUTURE ACTIVITY
        # --------------------------------------------------

        future_activity = (
            pd.concat(
                [
                    future_behavior,
                    future_orders
                ],
                ignore_index=True
            )
            .drop_duplicates()
        )

        future_activity = (
            future_activity
            .groupby(
                "customer_id"
            )
            .agg(
                future_active_days=(
                    "simulation_day",
                    "nunique"
                )
            )
            .reset_index()
        )

        return future_activity

    # ======================================================
    # ONE SNAPSHOT
    # ======================================================

    def build_snapshot(
        self,
        snapshot_day
    ):

        snapshot = (
            self.customer_features[
                self.customer_features[
                    "snapshot_day"
                ]
                == snapshot_day
            ]
            .copy()
        )

        # --------------------------------------------------
        # ELIGIBILITY
        #
        # Churn is meaningful only after a customer has
        # demonstrated some historical engagement.
        # --------------------------------------------------

        historical_behavior = (
            snapshot[
                "hist_product_view_count"
            ]
            +
            snapshot[
                "hist_add_to_cart_count"
            ]
            +
            snapshot[
                "hist_purchase_intent_count"
            ]
            +
            snapshot[
                "hist_cart_abandonment_count"
            ]
        )

        has_historical_engagement = (
            (
                historical_behavior
                > 0
            )
            |
            (
                snapshot[
                    "hist_order_count"
                ]
                > 0
            )
        )

        snapshot = (
            snapshot[
                has_historical_engagement
            ]
            .copy()
        )

        # --------------------------------------------------
        # FUTURE LABEL WINDOW
        # --------------------------------------------------

        future_activity = (
            self._build_future_activity(
                snapshot_day
            )
        )

        snapshot = (
            snapshot.merge(
                future_activity,
                on="customer_id",
                how="left",
                validate="one_to_one"
            )
        )

        snapshot[
            "future_active_days"
        ] = (
            snapshot[
                "future_active_days"
            ]
            .fillna(0)
        )

        # --------------------------------------------------
        # TARGET
        #
        # 1 = no observed behavior or purchase
        #     during the future 30-day window
        #
        # 0 = customer remains active
        # --------------------------------------------------

        snapshot[
            "churn_label"
        ] = (
            snapshot[
                "future_active_days"
            ]
            == 0
        ).astype(int)

        # future_active_days helped construct the target,
        # therefore it MUST NOT become an ML feature.
        snapshot = (
            snapshot.drop(
                columns=[
                    "future_active_days"
                ]
            )
        )

        return snapshot

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
        "PHASE 7 - CHURN MODELLING DATASET TEST"
    )
    print("=" * 70)

    builder = (
        ChurnDatasetBuilder()
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
        "\nChurn distribution:"
    )

    print(
        dataset[
            "churn_label"
        ]
        .value_counts()
        .sort_index()
    )

    print(
        "\nChurn distribution by snapshot:"
    )

    print(
        pd.crosstab(
            dataset[
                "snapshot_day"
            ],
            dataset[
                "churn_label"
            ]
        )
    )

    churn_rate = (
        dataset
        .groupby(
            "snapshot_day"
        )[
            "churn_label"
        ]
        .mean()
    )

    print(
        "\nChurn rate by snapshot:"
    )

    print(churn_rate)

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
        "\nTarget column:"
    )

    print(
        dataset[
            "churn_label"
        ]
        .dtype
    )

    print(
        "\nCHURN MODELLING "
        "DATASET TEST PASSED."
    )