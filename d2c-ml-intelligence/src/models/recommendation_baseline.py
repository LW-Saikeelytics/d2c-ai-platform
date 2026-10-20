import numpy as np
import pandas as pd

from src.data_loader import MLDataLoader

from src.datasets.recommendation_dataset import (
    RecommendationDatasetBuilder
)


class RecommendationBaselineModel:

    def __init__(self):

        self.loader = MLDataLoader()

        self.dataset_builder = (
            RecommendationDatasetBuilder()
        )

        self.interactions = (
            self.dataset_builder
            .build_dataset()
        )

        self.orders = (
            self.loader.load_ml_orders()
        )

        self.products = (
            self.loader.load_product_master()
        )

        self.snapshot_day = (
            self.dataset_builder.snapshot_day
        )

        config = (
            self.loader.config[
                "baseline_models"
            ][
                "recommendation"
            ]
        )

        self.top_k = (
            config[
                "top_k"
            ]
        )

        self.evaluation_end_day = (
            config[
                "evaluation_end_day"
            ]
        )

        self.product_ranking = None

    # ======================================================
    # TRAIN / POPULARITY RANKING
    # ======================================================

    def train(self):

        popularity = (
            self.interactions
            .groupby(
                "product_id"
            )
            .agg(
                interaction_score=(
                    "interaction_score",
                    "sum"
                ),

                interaction_customers=(
                    "customer_id",
                    "nunique"
                ),

                historical_purchases=(
                    "purchase_count",
                    "sum"
                )
            )
            .reset_index()
        )

        popularity = (
            self.products[
                [
                    "product_id",
                    "product_name",
                    "category"
                ]
            ]
            .merge(
                popularity,
                on="product_id",
                how="left",
                validate="one_to_one"
            )
        )

        numeric_columns = [
            "interaction_score",
            "interaction_customers",
            "historical_purchases"
        ]

        popularity[
            numeric_columns
        ] = (
            popularity[
                numeric_columns
            ]
            .fillna(0)
        )

        self.product_ranking = (
            popularity
            .sort_values(
                [
                    "interaction_score",
                    "interaction_customers",
                    "historical_purchases",
                    "product_id"
                ],
                ascending=[
                    False,
                    False,
                    False,
                    True
                ]
            )
            .reset_index(
                drop=True
            )
        )

        self.product_ranking[
            "popularity_rank"
        ] = (
            np.arange(
                len(
                    self.product_ranking
                )
            )
            + 1
        )

        return self.product_ranking

    # ======================================================
    # TOP-K RECOMMENDATIONS
    # ======================================================

    def get_top_products(self):

        if self.product_ranking is None:

            self.train()

        return (
            self.product_ranking
            .head(
                self.top_k
            )
            .copy()
        )

    # ======================================================
    # FUTURE PURCHASES
    # ======================================================

    def _future_orders(self):

        return (
            self.orders[
                (
                    self.orders[
                        "simulation_day"
                    ]
                    >
                    self.snapshot_day
                )
                &
                (
                    self.orders[
                        "simulation_day"
                    ]
                    <=
                    self.evaluation_end_day
                )
            ]
            .copy()
        )

    # ======================================================
    # EVALUATION
    # ======================================================

    def evaluate(self):

        top_products = (
            self.get_top_products()
        )

        recommended_products = (
            top_products[
                "product_id"
            ]
            .tolist()
        )

        recommended_set = set(
            recommended_products
        )

        future_orders = (
            self._future_orders()
        )

        future_customer_products = (
            future_orders
            .groupby(
                "customer_id"
            )[
                "product_id"
            ]
            .apply(
                lambda values:
                    set(values)
            )
        )

        rows = []

        for (
            customer_id,
            relevant_products
        ) in (
            future_customer_products.items()
        ):

            hits = (
                recommended_set
                &
                relevant_products
            )

            hit_count = (
                len(
                    hits
                )
            )

            hit_rate = int(
                hit_count > 0
            )

            recall = (
                hit_count
                /
                len(
                    relevant_products
                )
            )

            precision = (
                hit_count
                /
                self.top_k
            )

            reciprocal_rank = 0.0

            for rank, product_id in enumerate(
                recommended_products,
                start=1
            ):

                if product_id in (
                    relevant_products
                ):

                    reciprocal_rank = (
                        1.0 / rank
                    )

                    break

            rows.append(
                {
                    "customer_id":
                        customer_id,

                    "relevant_products":
                        len(
                            relevant_products
                        ),

                    "hits":
                        hit_count,

                    "hit_rate":
                        hit_rate,

                    "recall_at_k":
                        recall,

                    "precision_at_k":
                        precision,

                    "reciprocal_rank":
                        reciprocal_rank
                }
            )

        evaluation = (
            pd.DataFrame(
                rows
            )
        )

        catalog_size = (
            self.products[
                "product_id"
            ]
            .nunique()
        )

        coverage = (
            len(
                recommended_set
            )
            /
            catalog_size
        )

        return {
            "evaluation_customers":
                len(
                    evaluation
                ),

            "future_orders":
                len(
                    future_orders
                ),

            "future_unique_products":
                future_orders[
                    "product_id"
                ]
                .nunique(),

            "top_k":
                self.top_k,

            "hit_rate_at_k":
                float(
                    evaluation[
                        "hit_rate"
                    ]
                    .mean()
                ),

            "recall_at_k":
                float(
                    evaluation[
                        "recall_at_k"
                    ]
                    .mean()
                ),

            "precision_at_k":
                float(
                    evaluation[
                        "precision_at_k"
                    ]
                    .mean()
                ),

            "mrr_at_k":
                float(
                    evaluation[
                        "reciprocal_rank"
                    ]
                    .mean()
                ),

            "catalog_coverage":
                float(
                    coverage
                )
        }


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 70)

    print(
        "PHASE 7 - RECOMMENDATION "
        "BASELINE MODEL"
    )

    print("=" * 70)

    baseline = (
        RecommendationBaselineModel()
    )

    ranking = (
        baseline.train()
    )

    print(
        "\nTraining window:"
    )

    print(
        f"Day 1-{baseline.snapshot_day}"
    )

    print(
        "\nEvaluation window:"
    )

    print(
        f"Day "
        f"{baseline.snapshot_day + 1}"
        f"-{baseline.evaluation_end_day}"
    )

    print(
        "\nTop recommended products:"
    )

    print(
        baseline
        .get_top_products()[
            [
                "popularity_rank",
                "product_id",
                "product_name",
                "category",
                "interaction_score",
                "interaction_customers",
                "historical_purchases"
            ]
        ]
        .to_string(
            index=False
        )
    )

    print(
        "\nEvaluation metrics:"
    )

    metrics = (
        baseline.evaluate()
    )

    print(metrics)

    print(
        "\nRECOMMENDATION BASELINE "
        "MODEL TEST PASSED."
    )
    