import numpy as np
import pandas as pd

from src.data_loader import MLDataLoader


class RecommendationDatasetBuilder:

    EVENT_TYPES = [
        "product_view",
        "add_to_cart",
        "purchase_intent",
        "cart_abandonment"
    ]

    def __init__(self):

        self.loader = MLDataLoader()

        self.config = self.loader.config

        self.behavior = (
            self.loader
            .load_ml_behavior_history()
        )

        self.orders = (
            self.loader
            .load_ml_orders()
        )

        self.products = (
            self.loader
            .load_product_master()
        )

        recommendation_config = (
            self.config[
                "unsupervised_datasets"
            ][
                "recommendation"
            ]
        )

        self.snapshot_day = (
            recommendation_config[
                "snapshot_day"
            ]
        )

        self.weights = (
            recommendation_config[
                "interaction_weights"
            ]
        )

    # ======================================================
    # BEHAVIOR INTERACTIONS
    # ======================================================

    def _build_behavior_interactions(self):

        behavior = (
            self.behavior[
                self.behavior[
                    "simulation_day"
                ]
                <= self.snapshot_day
            ]
            .copy()
        )

        event_counts = (
            behavior
            .groupby(
                [
                    "customer_id",
                    "product_id",
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
            .reset_index()
            .rename(
                columns={
                    "product_view":
                        "product_view_count",

                    "add_to_cart":
                        "add_to_cart_count",

                    "purchase_intent":
                        "purchase_intent_count",

                    "cart_abandonment":
                        "cart_abandonment_count"
                }
            )
        )

        last_behavior = (
            behavior
            .groupby(
                [
                    "customer_id",
                    "product_id"
                ]
            )[
                "simulation_day"
            ]
            .max()
            .rename(
                "last_behavior_day"
            )
            .reset_index()
        )

        return (
            event_counts.merge(
                last_behavior,
                on=[
                    "customer_id",
                    "product_id"
                ],
                how="left",
                validate="one_to_one"
            )
        )

    # ======================================================
    # PURCHASE INTERACTIONS
    # ======================================================

    def _build_purchase_interactions(self):

        orders = (
            self.orders[
                self.orders[
                    "simulation_day"
                ]
                <= self.snapshot_day
            ]
            .copy()
        )

        purchases = (
            orders
            .groupby(
                [
                    "customer_id",
                    "product_id"
                ]
            )
            .agg(
                purchase_count=(
                    "order_id",
                    "count"
                ),

                units_purchased=(
                    "quantity",
                    "sum"
                ),

                purchase_value=(
                    "gross_amount",
                    "sum"
                ),

                purchase_days=(
                    "simulation_day",
                    "nunique"
                ),

                last_purchase_day=(
                    "simulation_day",
                    "max"
                )
            )
            .reset_index()
        )

        return purchases

    # ======================================================
    # BUILD DATASET
    # ======================================================

    def build_dataset(self):

        behavior = (
            self._build_behavior_interactions()
        )

        purchases = (
            self._build_purchase_interactions()
        )

        # --------------------------------------------------
        # OUTER MERGE
        #
        # Important:
        # preserve order-only customer/product pairs.
        # We already discovered that some valid frozen
        # orders do not have behavior_history records.
        # --------------------------------------------------

        dataset = (
            behavior.merge(
                purchases,
                on=[
                    "customer_id",
                    "product_id"
                ],
                how="outer",
                validate="one_to_one"
            )
        )

        # --------------------------------------------------
        # PRODUCT METADATA
        # --------------------------------------------------

        product_columns = [
            "product_id",
            "product_name",
            "category",
            "subcategory",
            "product_type",
            "price_band"
        ]

        dataset = (
            dataset.merge(
                self.products[
                    product_columns
                ],
                on="product_id",
                how="left",
                validate="many_to_one"
            )
        )

        # --------------------------------------------------
        # ZERO-FILL INTERACTION COUNTS
        # --------------------------------------------------

        count_columns = [
            "product_view_count",
            "add_to_cart_count",
            "purchase_intent_count",
            "cart_abandonment_count",
            "purchase_count",
            "units_purchased",
            "purchase_days",
            "purchase_value"
        ]

        dataset[
            count_columns
        ] = (
            dataset[
                count_columns
            ]
            .fillna(0)
        )

        # --------------------------------------------------
        # PURCHASE FLAG
        # --------------------------------------------------

        dataset[
            "purchased_flag"
        ] = (
            dataset[
                "purchase_count"
            ]
            > 0
        ).astype(int)

        # --------------------------------------------------
        # LAST INTERACTION
        # --------------------------------------------------

        dataset[
            "last_interaction_day"
        ] = (
            dataset[
                [
                    "last_behavior_day",
                    "last_purchase_day"
                ]
            ]
            .max(
                axis=1,
                skipna=True
            )
        )

        dataset[
            "days_since_last_interaction"
        ] = (
            self.snapshot_day
            -
            dataset[
                "last_interaction_day"
            ]
        )

        # Every row represents at least one
        # behavior or purchase interaction.
        if dataset[
            "last_interaction_day"
        ].isna().any():

            raise ValueError(
                "Recommendation pair has no "
                "interaction timestamp."
            )

        # --------------------------------------------------
        # IMPLICIT INTERACTION SCORE
        # --------------------------------------------------

        dataset[
            "interaction_score"
        ] = (
            dataset[
                "product_view_count"
            ]
            *
            self.weights[
                "product_view"
            ]
            +
            dataset[
                "add_to_cart_count"
            ]
            *
            self.weights[
                "add_to_cart"
            ]
            +
            dataset[
                "purchase_intent_count"
            ]
            *
            self.weights[
                "purchase_intent"
            ]
            +
            dataset[
                "cart_abandonment_count"
            ]
            *
            self.weights[
                "cart_abandonment"
            ]
            +
            dataset[
                "purchase_count"
            ]
            *
            self.weights[
                "purchase"
            ]
        )

        # Log-scaled score can later help models where
        # highly active users otherwise dominate.
        dataset[
            "interaction_score_log1p"
        ] = np.log1p(
            dataset[
                "interaction_score"
            ]
        )

        dataset[
            "snapshot_day"
        ] = self.snapshot_day

        # --------------------------------------------------
        # STABLE COLUMN ORDER
        # --------------------------------------------------

        columns = [
            "customer_id",
            "product_id",
            "snapshot_day",

            "product_name",
            "category",
            "subcategory",
            "product_type",
            "price_band",

            "product_view_count",
            "add_to_cart_count",
            "purchase_intent_count",
            "cart_abandonment_count",

            "purchase_count",
            "units_purchased",
            "purchase_days",
            "purchase_value",
            "purchased_flag",

            "last_behavior_day",
            "last_purchase_day",
            "last_interaction_day",
            "days_since_last_interaction",

            "interaction_score",
            "interaction_score_log1p"
        ]

        dataset = (
            dataset[
                columns
            ]
            .sort_values(
                [
                    "customer_id",
                    "product_id"
                ]
            )
            .reset_index(
                drop=True
            )
        )

        return dataset


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 70)
    print(
        "PHASE 7 - RECOMMENDATION DATASET TEST"
    )
    print("=" * 70)

    builder = (
        RecommendationDatasetBuilder()
    )

    dataset = (
        builder.build_dataset()
    )

    print(
        f"\nSnapshot day: "
        f"{builder.snapshot_day}"
    )

    print(
        f"\nInteraction rows: "
        f"{len(dataset):,}"
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

    print(
        "\nUnique products:"
    )

    print(
        dataset[
            "product_id"
        ]
        .nunique()
    )

    duplicates = (
        dataset
        .duplicated(
            subset=[
                "customer_id",
                "product_id"
            ]
        )
        .sum()
    )

    print(
        "\nDuplicate customer/product pairs:"
    )

    print(duplicates)

    print(
        "\nPurchased customer/product pairs:"
    )

    print(
        dataset[
            "purchased_flag"
        ]
        .sum()
    )

    print(
        "\nTotal purchase count:"
    )

    print(
        dataset[
            "purchase_count"
        ]
        .sum()
    )

    print(
        "\nTotal purchase value:"
    )

    print(
        dataset[
            "purchase_value"
        ]
        .sum()
    )

    print(
        "\nTotal behavior signals:"
    )

    behavior_total = (
        dataset[
            "product_view_count"
        ].sum()
        +
        dataset[
            "add_to_cart_count"
        ].sum()
        +
        dataset[
            "purchase_intent_count"
        ].sum()
        +
        dataset[
            "cart_abandonment_count"
        ].sum()
    )

    print(
        behavior_total
    )

    print(
        "\nInteraction score summary:"
    )

    print(
        dataset[
            "interaction_score"
        ]
        .describe()
    )

    print(
        "\nRECOMMENDATION DATASET "
        "TEST PASSED."
    )