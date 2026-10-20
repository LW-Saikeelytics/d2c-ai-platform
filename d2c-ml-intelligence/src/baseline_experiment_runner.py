from src.experiment_tracker import (
    ExperimentTracker
)

from src.models.churn_baseline import (
    ChurnBaselineModel
)

from src.models.propensity_baseline import (
    PropensityBaselineModel
)

from src.models.clv_baseline import (
    CLVBaselineModel
)

from src.models.segmentation_baseline import (
    SegmentationBaselineModel
)

from src.models.recommendation_baseline import (
    RecommendationBaselineModel
)


class BaselineExperimentRunner:

    def __init__(self):

        self.tracker = (
            ExperimentTracker()
        )

        self.records = []

    # ======================================================
    # CHURN
    # ======================================================

    def run_churn(self):

        baseline = (
            ChurnBaselineModel()
        )

        training = (
            baseline.train()
        )

        train_metrics = (
            baseline.evaluate(
                baseline.train_day
            )
        )

        validation_metrics = (
            baseline.evaluate(
                baseline.validation_day
            )
        )

        test_metrics = (
            baseline.evaluate(
                baseline.test_day
            )
        )

        record = (
            self.tracker.log_experiment(
                model_name=(
                    "churn_logistic_regression_baseline"
                ),

                model_type=(
                    "classification"
                ),

                dataset=(
                    "churn_modelling_dataset"
                ),

                train_snapshot=(
                    baseline.train_day
                ),

                validation_snapshot=(
                    baseline.validation_day
                ),

                test_snapshot=(
                    baseline.test_day
                ),

                parameters={
                    "algorithm":
                        "LogisticRegression",

                    "class_weight":
                        "balanced",

                    "max_iter":
                        2000,

                    "random_state":
                        42,

                    "decision_threshold":
                        0.5,

                    "training_configuration":
                        training
                },

                metrics={
                    "train":
                        train_metrics,

                    "validation":
                        validation_metrics,

                    "test":
                        test_metrics
                },

                notes=(
                    "Temporal churn baseline. "
                    "Generator-authored latent "
                    "features excluded."
                )
            )
        )

        self.records.append(
            record
        )

    # ======================================================
    # PURCHASE PROPENSITY
    # ======================================================

    def run_propensity(self):

        baseline = (
            PropensityBaselineModel()
        )

        training = (
            baseline.train()
        )

        train_metrics = (
            baseline.evaluate(
                baseline.train_day
            )
        )

        validation_metrics = (
            baseline.evaluate(
                baseline.validation_day
            )
        )

        test_metrics = (
            baseline.evaluate(
                baseline.test_day
            )
        )

        record = (
            self.tracker.log_experiment(
                model_name=(
                    "purchase_propensity_logistic_regression_baseline"
                ),

                model_type=(
                    "classification"
                ),

                dataset=(
                    "purchase_propensity_dataset"
                ),

                train_snapshot=(
                    baseline.train_day
                ),

                validation_snapshot=(
                    baseline.validation_day
                ),

                test_snapshot=(
                    baseline.test_day
                ),

                parameters={
                    "algorithm":
                        "LogisticRegression",

                    "class_weight":
                        "balanced",

                    "max_iter":
                        2000,

                    "random_state":
                        42,

                    "decision_threshold":
                        0.5,

                    "training_configuration":
                        training
                },

                metrics={
                    "train":
                        train_metrics,

                    "validation":
                        validation_metrics,

                    "test":
                        test_metrics
                },

                notes=(
                    "Temporal purchase-propensity "
                    "baseline. Sparse positive "
                    "class; PR-AUC is a primary "
                    "evaluation metric."
                )
            )
        )

        self.records.append(
            record
        )

    # ======================================================
    # CLV
    # ======================================================

    def run_clv(self):

        baseline = (
            CLVBaselineModel()
        )

        training = (
            baseline.train()
        )

        train_metrics = (
            baseline.evaluate(
                baseline.train_day
            )
        )

        validation_metrics = (
            baseline.evaluate(
                baseline.validation_day
            )
        )

        test_metrics = (
            baseline.evaluate(
                baseline.test_day
            )
        )

        record = (
            self.tracker.log_experiment(
                model_name=(
                    "clv_random_forest_baseline"
                ),

                model_type=(
                    "regression"
                ),

                dataset=(
                    "clv_30d_dataset"
                ),

                train_snapshot=(
                    baseline.train_day
                ),

                validation_snapshot=(
                    baseline.validation_day
                ),

                test_snapshot=(
                    baseline.test_day
                ),

                parameters={
                    "algorithm":
                        "RandomForestRegressor",

                    "n_estimators":
                        200,

                    "max_depth":
                        12,

                    "min_samples_leaf":
                        5,

                    "random_state":
                        42,

                    "training_configuration":
                        training
                },

                metrics={
                    "train":
                        train_metrics,

                    "validation":
                        validation_metrics,

                    "test":
                        test_metrics
                },

                notes=(
                    "Single-stage 30-day customer "
                    "value regression baseline. "
                    "Zero-value benchmark retained "
                    "for comparison."
                )
            )
        )

        self.records.append(
            record
        )

    # ======================================================
    # SEGMENTATION
    # ======================================================

    def run_segmentation(self):

        baseline = (
            SegmentationBaselineModel()
        )

        preparation = (
            baseline.prepare_features()
        )

        candidates = (
            baseline
            .evaluate_cluster_counts()
        )

        best_k = (
            baseline.select_best_k()
        )

        baseline.fit_best_model()

        cluster_sizes = (
            baseline
            .get_cluster_sizes()
            .reset_index()
        )

        cluster_profiles = (
            baseline
            .get_cluster_profiles()
            .reset_index()
        )

        selected_result = (
            candidates[
                candidates[
                    "k"
                ]
                == best_k
            ]
            .iloc[0]
            .to_dict()
        )

        record = (
            self.tracker.log_experiment(
                model_name=(
                    "customer_kmeans_segmentation_baseline"
                ),

                model_type=(
                    "clustering"
                ),

                dataset=(
                    "customer_segmentation_dataset"
                ),

                train_snapshot=(
                    baseline.dataset_builder
                    .snapshot_day
                ),

                parameters={
                    "algorithm":
                        "KMeans",

                    "candidate_clusters":
                        baseline.candidate_clusters,

                    "selected_k":
                        best_k,

                    "n_init":
                        10,

                    "random_state":
                        baseline.random_state,

                    "silhouette_sample_size":
                        baseline
                        .silhouette_sample_size,

                    "dataset_configuration":
                        preparation
                },

                metrics={
                    "selected_cluster_result":
                        selected_result,

                    "candidate_evaluation":
                        candidates.to_dict(
                            orient="records"
                        ),

                    "cluster_sizes":
                        cluster_sizes.to_dict(
                            orient="records"
                        ),

                    "cluster_profiles":
                        cluster_profiles.to_dict(
                            orient="records"
                        )
                },

                notes=(
                    "K-Means baseline using "
                    "standardized observable "
                    "customer features. Existing "
                    "synthetic segment labels were "
                    "not used as clustering inputs."
                )
            )
        )

        self.records.append(
            record
        )

    # ======================================================
    # RECOMMENDATION
    # ======================================================

    def run_recommendation(self):

        baseline = (
            RecommendationBaselineModel()
        )

        ranking = (
            baseline.train()
        )

        metrics = (
            baseline.evaluate()
        )

        top_products = (
            ranking
            .head(
                baseline.top_k
            )[
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
            .to_dict(
                orient="records"
            )
        )

        record = (
            self.tracker.log_experiment(
                model_name=(
                    "global_popularity_recommendation_baseline"
                ),

                model_type=(
                    "recommendation"
                ),

                dataset=(
                    "recommendation_interaction_dataset"
                ),

                train_snapshot=(
                    baseline.snapshot_day
                ),

                test_snapshot=(
                    baseline.evaluation_end_day
                ),

                parameters={
                    "algorithm":
                        "GlobalPopularity",

                    "top_k":
                        baseline.top_k,

                    "training_end_day":
                        baseline.snapshot_day,

                    "evaluation_end_day":
                        baseline.evaluation_end_day,

                    "interaction_weights":
                        baseline
                        .dataset_builder
                        .weights
                },

                metrics={
                    **metrics,

                    "top_products":
                        top_products
                },

                notes=(
                    "Non-personalized popularity "
                    "baseline. Future purchases from "
                    "Days 61-90 used for evaluation."
                )
            )
        )

        self.records.append(
            record
        )

    # ======================================================
    # RUN ALL
    # ======================================================

    def run_all(self):

        self.run_churn()
        self.run_propensity()
        self.run_clv()
        self.run_segmentation()
        self.run_recommendation()

        return self.records


# ==========================================================
# MAIN
# ==========================================================

if __name__ == "__main__":

    print("=" * 70)
    print(
        "PHASE 7 - BASELINE EXPERIMENT REGISTRATION"
    )
    print("=" * 70)

    runner = (
        BaselineExperimentRunner()
    )

    records = (
        runner.run_all()
    )

    print(
        "\nExperiments registered:"
    )

    for record in records:

        print(
            record[
                "experiment_id"
            ],
            "|",
            record[
                "model_name"
            ]
        )

    history = (
        runner.tracker
        .load_history()
    )

    print(
        "\nTotal experiments in registry:"
    )

    print(
        len(history)
    )

    print(
        "\nRegistered model names:"
    )

    for record in history:

        print(
            "-",
            record[
                "model_name"
            ]
        )

    print(
        "\nJSONL:"
    )

    print(
        runner.tracker.jsonl_path
    )

    print(
        "\nCSV:"
    )

    print(
        runner.tracker.csv_path
    )

    print(
        "\nBASELINE EXPERIMENT "
        "REGISTRATION PASSED."
    )
    