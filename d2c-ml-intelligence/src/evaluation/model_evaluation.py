from src.experiment_tracker import (
    ExperimentTracker
)


class ModelEvaluation:

    REQUIRED_MODELS = {
        "churn_logistic_regression_baseline",
        "purchase_propensity_logistic_regression_baseline",
        "clv_random_forest_baseline",
        "customer_kmeans_segmentation_baseline",
        "global_popularity_recommendation_baseline"
    }

    def __init__(self):

        self.tracker = (
            ExperimentTracker()
        )

        self.history = (
            self.tracker.load_history()
        )

        self.by_model = {
            record[
                "model_name"
            ]:
            record
            for record
            in self.history
        }

        self.errors = []

    # ======================================================
    # REGISTRY VALIDATION
    # ======================================================

    def validate_registry(self):

        available = set(
            self.by_model.keys()
        )

        missing = (
            self.REQUIRED_MODELS
            -
            available
        )

        if missing:

            self.errors.append(
                "Missing required baseline "
                f"experiments: {sorted(missing)}"
            )

        return {
            "passed":
                len(self.errors) == 0,

            "error_count":
                len(self.errors),

            "errors":
                self.errors
        }

    # ======================================================
    # CHURN
    # ======================================================

    def evaluate_churn(self):

        record = (
            self.by_model[
                "churn_logistic_regression_baseline"
            ]
        )

        test = (
            record[
                "metrics"
            ][
                "test"
            ]
        )

        actual_rate = (
            test[
                "actual_churn_rate"
            ]
        )

        return {
            "model":
                "Churn",

            "roc_auc":
                test[
                    "roc_auc"
                ],

            "pr_auc":
                test[
                    "pr_auc"
                ],

            "precision":
                test[
                    "precision"
                ],

            "recall":
                test[
                    "recall"
                ],

            "f1":
                test[
                    "f1"
                ],

            "actual_rate":
                actual_rate,

            "predicted_rate":
                test[
                    "predicted_churn_rate"
                ],

            "assessment":
                (
                    "useful_baseline"
                    if test[
                        "roc_auc"
                    ] > 0.60
                    else
                    "weak_baseline"
                )
        }

    # ======================================================
    # PROPENSITY
    # ======================================================

    def evaluate_propensity(self):

        record = (
            self.by_model[
                "purchase_propensity_logistic_regression_baseline"
            ]
        )

        test = (
            record[
                "metrics"
            ][
                "test"
            ]
        )

        positive_rate = (
            test[
                "actual_purchase_rate"
            ]
        )

        pr_lift = (
            test[
                "pr_auc"
            ]
            /
            positive_rate
        )

        return {
            "model":
                "Purchase Propensity",

            "roc_auc":
                test[
                    "roc_auc"
                ],

            "pr_auc":
                test[
                    "pr_auc"
                ],

            "positive_rate":
                positive_rate,

            "pr_auc_lift_vs_prevalence":
                pr_lift,

            "precision":
                test[
                    "precision"
                ],

            "recall":
                test[
                    "recall"
                ],

            "f1":
                test[
                    "f1"
                ],

            "assessment":
                (
                    "strong_baseline"
                    if (
                        test[
                            "roc_auc"
                        ] >= 0.80
                        and
                        pr_lift >= 3.0
                    )
                    else
                    "useful_baseline"
                )
        }

    # ======================================================
    # CLV
    # ======================================================

    def evaluate_clv(self):

        record = (
            self.by_model[
                "clv_random_forest_baseline"
            ]
        )

        test = (
            record[
                "metrics"
            ][
                "test"
            ]
        )

        beats_zero_mae = (
            test[
                "mae"
            ]
            <
            test[
                "zero_baseline_mae"
            ]
        )

        beats_zero_rmse = (
            test[
                "rmse"
            ]
            <
            test[
                "zero_baseline_rmse"
            ]
        )

        return {
            "model":
                "30-Day CLV",

            "mae":
                test[
                    "mae"
                ],

            "rmse":
                test[
                    "rmse"
                ],

            "r2":
                test[
                    "r2"
                ],

            "zero_baseline_mae":
                test[
                    "zero_baseline_mae"
                ],

            "zero_baseline_rmse":
                test[
                    "zero_baseline_rmse"
                ],

            "beats_zero_mae":
                beats_zero_mae,

            "beats_zero_rmse":
                beats_zero_rmse,

            "assessment":
                (
                    "useful_but_needs_two_stage_model"
                    if (
                        test[
                            "r2"
                        ] > 0
                        and
                        not beats_zero_mae
                    )
                    else
                    "useful_baseline"
                )
        }

    # ======================================================
    # SEGMENTATION
    # ======================================================

    def evaluate_segmentation(self):

        record = (
            self.by_model[
                "customer_kmeans_segmentation_baseline"
            ]
        )

        result = (
            record[
                "metrics"
            ][
                "selected_cluster_result"
            ]
        )

        parameters = (
            record[
                "parameters"
            ]
        )

        return {
            "model":
                "Customer Segmentation",

            "selected_k":
                parameters[
                    "selected_k"
                ],

            "silhouette_score":
                result[
                    "silhouette_score"
                ],

            "davies_bouldin_score":
                result[
                    "davies_bouldin_score"
                ],

            "calinski_harabasz_score":
                result[
                    "calinski_harabasz_score"
                ],

            "smallest_cluster":
                result[
                    "smallest_cluster"
                ],

            "largest_cluster":
                result[
                    "largest_cluster"
                ],

            "assessment":
                (
                    "clear_baseline_structure"
                    if result[
                        "silhouette_score"
                    ] >= 0.50
                    else
                    "moderate_structure"
                )
        }

    # ======================================================
    # RECOMMENDATION
    # ======================================================

    def evaluate_recommendation(self):

        record = (
            self.by_model[
                "global_popularity_recommendation_baseline"
            ]
        )

        metrics = (
            record[
                "metrics"
            ]
        )

        return {
            "model":
                "Recommendation",

            "top_k":
                metrics[
                    "top_k"
                ],

            "hit_rate_at_k":
                metrics[
                    "hit_rate_at_k"
                ],

            "recall_at_k":
                metrics[
                    "recall_at_k"
                ],

            "precision_at_k":
                metrics[
                    "precision_at_k"
                ],

            "mrr_at_k":
                metrics[
                    "mrr_at_k"
                ],

            "catalog_coverage":
                metrics[
                    "catalog_coverage"
                ],

            "assessment":
                "valid_popularity_floor"
        }

    # ======================================================
    # FINAL SUMMARY
    # ======================================================

    def build_summary(self):

        validation = (
            self.validate_registry()
        )

        if not validation[
            "passed"
        ]:

            raise ValueError(
                validation
            )

        return {
            "churn":
                self.evaluate_churn(),

            "propensity":
                self.evaluate_propensity(),

            "clv":
                self.evaluate_clv(),

            "segmentation":
                self.evaluate_segmentation(),

            "recommendation":
                self.evaluate_recommendation()
        }


if __name__ == "__main__":

    print("=" * 70)
    print(
        "PHASE 7 - BASELINE MODEL EVALUATION"
    )
    print("=" * 70)

    evaluation = (
        ModelEvaluation()
    )

    registry_validation = (
        evaluation.validate_registry()
    )

    print(
        "\nRegistry validation:"
    )

    print(
        registry_validation
    )

    summary = (
        evaluation.build_summary()
    )

    print(
        "\nCHURN:"
    )

    print(
        summary[
            "churn"
        ]
    )

    print(
        "\nPURCHASE PROPENSITY:"
    )

    print(
        summary[
            "propensity"
        ]
    )

    print(
        "\nCLV:"
    )

    print(
        summary[
            "clv"
        ]
    )

    print(
        "\nCUSTOMER SEGMENTATION:"
    )

    print(
        summary[
            "segmentation"
        ]
    )

    print(
        "\nRECOMMENDATION:"
    )

    print(
        summary[
            "recommendation"
        ]
    )

    print(
        "\nBASELINE MODEL "
        "EVALUATION PASSED."
    )