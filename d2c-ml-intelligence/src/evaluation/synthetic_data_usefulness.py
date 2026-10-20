import json

from pathlib import Path

import numpy as np

from src.data_loader import (
    MLDataLoader
)

from src.datasets.churn_dataset import (
    ChurnDatasetBuilder
)

from src.datasets.propensity_dataset import (
    PropensityDatasetBuilder
)

from src.datasets.clv_dataset import (
    CLVDatasetBuilder
)

from src.datasets.segmentation_dataset import (
    SegmentationDatasetBuilder
)

from src.datasets.recommendation_dataset import (
    RecommendationDatasetBuilder
)

from src.evaluation.model_evaluation import (
    ModelEvaluation
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)


class SyntheticDataUsefulnessEvaluation:

    def __init__(self):

        self.loader = (
            MLDataLoader()
        )

        # --------------------------------------------------
        # RAW FROZEN SOURCE
        # --------------------------------------------------

        self.raw_customers = (
            self.loader.load_customers()
        )

        self.raw_orders = (
            self.loader.load_orders()
        )

        self.raw_behavior = (
            self.loader
            .load_behavior_history()
        )

        self.products = (
            self.loader.load_product_master()
        )

        # --------------------------------------------------
        # ML-SAFE SOURCE
        # --------------------------------------------------

        self.ml_orders = (
            self.loader.load_ml_orders()
        )

        self.ml_behavior = (
            self.loader
            .load_ml_behavior_history()
        )

        # --------------------------------------------------
        # TRAINING DATASETS
        # --------------------------------------------------

        self.churn = (
            ChurnDatasetBuilder()
            .build_dataset()
        )

        self.propensity = (
            PropensityDatasetBuilder()
            .build_dataset()
        )

        self.clv = (
            CLVDatasetBuilder()
            .build_dataset()
        )

        segmentation_builder = (
            SegmentationDatasetBuilder()
        )

        self.segmentation = (
            segmentation_builder
            .build_dataset()
        )

        self.segmentation_features = (
            segmentation_builder
            .get_feature_columns()
        )

        self.recommendation = (
            RecommendationDatasetBuilder()
            .build_dataset()
        )

        # --------------------------------------------------
        # MODEL EVALUATION
        # --------------------------------------------------

        self.model_summary = (
            ModelEvaluation()
            .build_summary()
        )

        self.report = None

    # ======================================================
    # SOURCE QUALITY FINDINGS
    # ======================================================

    def _prelaunch_count(
        self,
        dataframe
    ):

        product_launch = (
            self.products[
                [
                    "product_id",
                    "launch_day"
                ]
            ]
        )

        merged = (
            dataframe.merge(
                product_launch,
                on="product_id",
                how="left",
                validate="many_to_one"
            )
        )

        invalid = (
            merged[
                "simulation_day"
            ]
            <
            merged[
                "launch_day"
            ]
        )

        return int(
            invalid.sum()
        )

    def evaluate_source_quality(self):

        raw_prelaunch_behavior = (
            self._prelaunch_count(
                self.raw_behavior
            )
        )

        raw_prelaunch_orders = (
            self._prelaunch_count(
                self.raw_orders
            )
        )

        cleaned_prelaunch_behavior = (
            self._prelaunch_count(
                self.ml_behavior
            )
        )

        cleaned_prelaunch_orders = (
            self._prelaunch_count(
                self.ml_orders
            )
        )

        behavior_days = (
            self.ml_behavior[
                [
                    "customer_id",
                    "simulation_day"
                ]
            ]
            .drop_duplicates()
        )

        order_days = (
            self.ml_orders[
                [
                    "customer_id",
                    "simulation_day"
                ]
            ]
            .drop_duplicates()
        )

        order_day_check = (
            order_days.merge(
                behavior_days,
                on=[
                    "customer_id",
                    "simulation_day"
                ],
                how="left",
                indicator=True
            )
        )

        order_days_without_behavior = int(
            (
                order_day_check[
                    "_merge"
                ]
                ==
                "left_only"
            ).sum()
        )

        max_day = int(
            max(
                self.ml_behavior[
                    "simulation_day"
                ].max(),

                self.ml_orders[
                    "simulation_day"
                ].max()
            )
        )

        return {
            "customers":
                int(
                    len(
                        self.raw_customers
                    )
                ),

            "products":
                int(
                    len(
                        self.products
                    )
                ),

            "simulation_horizon_days":
                max_day,

            "raw_prelaunch_behavior_rows":
                raw_prelaunch_behavior,

            "raw_prelaunch_order_rows":
                raw_prelaunch_orders,

            "ml_safe_prelaunch_behavior_rows":
                cleaned_prelaunch_behavior,

            "ml_safe_prelaunch_order_rows":
                cleaned_prelaunch_orders,

            "valid_order_days_without_behavior":
                order_days_without_behavior,

            "temporal_filter_successful":
                (
                    cleaned_prelaunch_behavior
                    == 0
                    and
                    cleaned_prelaunch_orders
                    == 0
                )
        }

    # ======================================================
    # DATASET USABILITY
    # ======================================================

    def evaluate_dataset_usability(self):

        churn_rates = (
            self.churn
            .groupby(
                "snapshot_day"
            )[
                "churn_label"
            ]
            .mean()
            .to_dict()
        )

        propensity_rates = (
            self.propensity
            .groupby(
                "snapshot_day"
            )[
                "purchase_propensity_label"
            ]
            .mean()
            .to_dict()
        )

        clv_positive_rates = (
            self.clv
            .assign(
                positive=(
                    self.clv[
                        "future_customer_value_30d"
                    ]
                    > 0
                ).astype(int)
            )
            .groupby(
                "snapshot_day"
            )[
                "positive"
            ]
            .mean()
            .to_dict()
        )

        segmentation_missing = int(
            self.segmentation[
                self.segmentation_features
            ]
            .isna()
            .sum()
            .sum()
        )

        return {
            "churn": {
                "rows":
                    int(
                        len(
                            self.churn
                        )
                    ),

                "snapshot_rates":
                    {
                        str(key):
                            float(value)
                        for key, value
                        in churn_rates.items()
                    },

                "both_classes_present":
                    bool(
                        self.churn[
                            "churn_label"
                        ]
                        .nunique()
                        == 2
                    )
            },

            "propensity": {
                "rows":
                    int(
                        len(
                            self.propensity
                        )
                    ),

                "positive_rows":
                    int(
                        self.propensity[
                            "purchase_propensity_label"
                        ]
                        .sum()
                    ),

                "snapshot_rates":
                    {
                        str(key):
                            float(value)
                        for key, value
                        in propensity_rates.items()
                    },

                "both_classes_present":
                    bool(
                        self.propensity[
                            "purchase_propensity_label"
                        ]
                        .nunique()
                        == 2
                    )
            },

            "clv": {
                "rows":
                    int(
                        len(
                            self.clv
                        )
                    ),

                "positive_value_rows":
                    int(
                        (
                            self.clv[
                                "future_customer_value_30d"
                            ]
                            > 0
                        ).sum()
                    ),

                "snapshot_positive_rates":
                    {
                        str(key):
                            float(value)
                        for key, value
                        in clv_positive_rates.items()
                    },

                "maximum_target_value":
                    float(
                        self.clv[
                            "future_customer_value_30d"
                        ]
                        .max()
                    )
            },

            "segmentation": {
                "rows":
                    int(
                        len(
                            self.segmentation
                        )
                    ),

                "features":
                    int(
                        len(
                            self.segmentation_features
                        )
                    ),

                "missing_feature_values":
                    segmentation_missing
            },

            "recommendation": {
                "interaction_rows":
                    int(
                        len(
                            self.recommendation
                        )
                    ),

                "customers":
                    int(
                        self.recommendation[
                            "customer_id"
                        ]
                        .nunique()
                    ),

                "products":
                    int(
                        self.recommendation[
                            "product_id"
                        ]
                        .nunique()
                    )
            }
        }

    # ======================================================
    # LEARNABILITY
    # ======================================================

    def evaluate_learnability(self):

        churn = (
            self.model_summary[
                "churn"
            ]
        )

        propensity = (
            self.model_summary[
                "propensity"
            ]
        )

        clv = (
            self.model_summary[
                "clv"
            ]
        )

        segmentation = (
            self.model_summary[
                "segmentation"
            ]
        )

        recommendation = (
            self.model_summary[
                "recommendation"
            ]
        )

        return {
            "churn_signal_present":
                bool(
                    churn[
                        "roc_auc"
                    ]
                    > 0.60
                ),

            "churn_test_roc_auc":
                float(
                    churn[
                        "roc_auc"
                    ]
                ),

            "propensity_signal_present":
                bool(
                    propensity[
                        "roc_auc"
                    ]
                    >= 0.80
                    and
                    propensity[
                        "pr_auc_lift_vs_prevalence"
                    ]
                    >= 3.0
                ),

            "propensity_test_roc_auc":
                float(
                    propensity[
                        "roc_auc"
                    ]
                ),

            "propensity_pr_auc_lift":
                float(
                    propensity[
                        "pr_auc_lift_vs_prevalence"
                    ]
                ),

            "clv_contains_predictive_signal":
                bool(
                    clv[
                        "r2"
                    ]
                    > 0
                ),

            "clv_test_r2":
                float(
                    clv[
                        "r2"
                    ]
                ),

            "clv_beats_zero_mae":
                bool(
                    clv[
                        "beats_zero_mae"
                    ]
                ),

            "clv_beats_zero_rmse":
                bool(
                    clv[
                        "beats_zero_rmse"
                    ]
                ),

            "segmentation_structure_present":
                bool(
                    segmentation[
                        "silhouette_score"
                    ]
                    >= 0.50
                ),

            "segmentation_silhouette":
                float(
                    segmentation[
                        "silhouette_score"
                    ]
                ),

            "recommendation_signal_present":
                bool(
                    recommendation[
                        "hit_rate_at_k"
                    ]
                    > 0.20
                ),

            "recommendation_hit_rate_at_5":
                float(
                    recommendation[
                        "hit_rate_at_k"
                    ]
                )
        }

    # ======================================================
    # READINESS CHECKS
    # ======================================================

    def build_readiness_checks(
        self,
        source,
        datasets,
        learnability
    ):

        checks = {
            "customer_scale_sufficient":
                source[
                    "customers"
                ]
                >= 10000,

            "temporal_horizon_sufficient":
                source[
                    "simulation_horizon_days"
                ]
                >= 90,

            "catalog_available":
                source[
                    "products"
                ]
                > 1,

            "ml_temporal_filter_clean":
                source[
                    "temporal_filter_successful"
                ],

            "churn_dataset_usable":
                (
                    datasets[
                        "churn"
                    ][
                        "rows"
                    ]
                    > 1000
                    and
                    datasets[
                        "churn"
                    ][
                        "both_classes_present"
                    ]
                ),

            "propensity_dataset_usable":
                (
                    datasets[
                        "propensity"
                    ][
                        "positive_rows"
                    ]
                    > 100
                    and
                    datasets[
                        "propensity"
                    ][
                        "both_classes_present"
                    ]
                ),

            "clv_dataset_usable":
                (
                    datasets[
                        "clv"
                    ][
                        "positive_value_rows"
                    ]
                    > 100
                ),

            "segmentation_dataset_usable":
                (
                    datasets[
                        "segmentation"
                    ][
                        "rows"
                    ]
                    == 10000
                    and
                    datasets[
                        "segmentation"
                    ][
                        "missing_feature_values"
                    ]
                    == 0
                ),

            "recommendation_dataset_usable":
                (
                    datasets[
                        "recommendation"
                    ][
                        "interaction_rows"
                    ]
                    > 1000
                    and
                    datasets[
                        "recommendation"
                    ][
                        "products"
                    ]
                    > 1
                ),

            "supervised_signal_present":
                (
                    learnability[
                        "churn_signal_present"
                    ]
                    and
                    learnability[
                        "propensity_signal_present"
                    ]
                ),

            "unsupervised_structure_present":
                learnability[
                    "segmentation_structure_present"
                ],

            "recommendation_signal_present":
                learnability[
                    "recommendation_signal_present"
                ]
        }

        return {
            key:
                bool(value)
            for key, value
            in checks.items()
        }

    # ======================================================
    # BUILD REPORT
    # ======================================================

    def build_report(self):

        source = (
            self.evaluate_source_quality()
        )

        datasets = (
            self.evaluate_dataset_usability()
        )

        learnability = (
            self.evaluate_learnability()
        )

        readiness = (
            self.build_readiness_checks(
                source,
                datasets,
                learnability
            )
        )

        passed_checks = (
            sum(
                readiness.values()
            )
        )

        total_checks = (
            len(
                readiness
            )
        )

        overall_ready = (
            passed_checks
            ==
            total_checks
        )

        limitations = [
            (
                "The frozen source contains "
                f"{source['raw_prelaunch_behavior_rows']} "
                "pre-launch behavior rows and "
                f"{source['raw_prelaunch_order_rows']} "
                "pre-launch orders. Phase 7 filters "
                "these before ML use."
            ),

            (
                "The frozen source contains "
                f"{source['valid_order_days_without_behavior']} "
                "valid order-days without matching "
                "behavior-history days. Phase 7 "
                "preserves these conversions using "
                "outer-merge logic."
            ),

            (
                "The observation horizon is only "
                f"{source['simulation_horizon_days']} days, "
                "so the CLV target is a 30-day "
                "forward value proxy rather than "
                "true long-term lifetime value."
            ),

            (
                "The recommendation catalog contains "
                f"{source['products']} products, so "
                "recommendation results are useful "
                "for baseline engineering but not "
                "representative of a large real-world "
                "catalog."
            ),

            (
                "Synthetic generator rules can create "
                "learnable relationships that may be "
                "stronger or cleaner than real-world "
                "relationships."
            ),

            (
                "No real customer dataset is available "
                "for external distributional or "
                "out-of-domain validation."
            ),

            (
                "The single-stage CLV regressor does "
                "not beat the zero-value baseline on "
                "MAE, supporting a future two-stage "
                "purchase-probability plus conditional-"
                "value approach."
            ),

            (
                "An anomaly/fraud dataset was "
                "intentionally skipped because the "
                "source does not contain sufficiently "
                "authentic fraud-related signals."
            )
        ]

        strengths = [
            (
                "Point-in-time customer, product, "
                "behavior and conversion features "
                "can be constructed without using "
                "future outcomes."
            ),

            (
                "Churn, purchase-propensity and "
                "30-day customer-value targets can "
                "be generated from future windows."
            ),

            (
                "The data contains measurable "
                "predictive signal for churn and "
                "purchase propensity."
            ),

            (
                "Customer behavior contains clear "
                "unsupervised cluster structure."
            ),

            (
                "Customer-product interactions support "
                "offline recommendation evaluation."
            ),

            (
                "Generator-authored latent variables "
                "and final status fields were excluded "
                "from baseline model inputs."
            ),

            (
                "Source inconsistencies discovered "
                "during ML preparation are explicitly "
                "handled rather than silently ignored."
            )
        ]

        self.report = {
            "evaluation_name":
                "Phase 7 Synthetic Data Usefulness Evaluation",

            "source_quality":
                source,

            "dataset_usability":
                datasets,

            "learnability":
                learnability,

            "readiness_checks":
                readiness,

            "passed_checks":
                passed_checks,

            "total_checks":
                total_checks,

            "all_readiness_checks_passed":
                overall_ready,

            "strengths":
                strengths,

            "limitations":
                limitations,

            "overall_assessment":
                (
                    "FIT_FOR_PHASE_7_ML_BASELINES_AND_"
                    "DOWNSTREAM_PLATFORM_DEVELOPMENT"
                    if overall_ready
                    else
                    "REQUIRES_ADDITIONAL_REMEDIATION"
                ),

            "real_world_validity_statement":
                (
                    "Baseline performance on this "
                    "synthetic dataset demonstrates "
                    "engineering and modelling "
                    "usefulness. It does not establish "
                    "real-world production model "
                    "performance or external validity."
                )
        }

        return self.report

    # ======================================================
    # SAVE REPORT
    # ======================================================

    def save_report(self):

        if self.report is None:

            self.build_report()

        output_path = (
            PROJECT_ROOT
            / "experiments"
            / "synthetic_data_usefulness_report.json"
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with output_path.open(
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                self.report,
                file,
                indent=2,
                ensure_ascii=False
            )

        return output_path


# ==========================================================
# MAIN
# ==========================================================

if __name__ == "__main__":

    print("=" * 70)
    print(
        "PHASE 7 - SYNTHETIC DATA "
        "USEFULNESS EVALUATION"
    )
    print("=" * 70)

    evaluation = (
        SyntheticDataUsefulnessEvaluation()
    )

    report = (
        evaluation.build_report()
    )

    print(
        "\nSOURCE QUALITY:"
    )

    print(
        report[
            "source_quality"
        ]
    )

    print(
        "\nDATASET USABILITY:"
    )

    print(
        report[
            "dataset_usability"
        ]
    )

    print(
        "\nLEARNABILITY:"
    )

    print(
        report[
            "learnability"
        ]
    )

    print(
        "\nREADINESS CHECKS:"
    )

    for (
        check,
        passed
    ) in (
        report[
            "readiness_checks"
        ].items()
    ):

        print(
            f"{check}: "
            f"{'PASS' if passed else 'FAIL'}"
        )

    print(
        "\nREADINESS SUMMARY:"
    )

    print(
        f"{report['passed_checks']}"
        f"/"
        f"{report['total_checks']} "
        "checks passed"
    )

    print(
        "\nOVERALL ASSESSMENT:"
    )

    print(
        report[
            "overall_assessment"
        ]
    )

    print(
        "\nKNOWN LIMITATIONS:"
    )

    for limitation in (
        report[
            "limitations"
        ]
    ):

        print(
            "-",
            limitation
        )

    output_path = (
        evaluation.save_report()
    )

    print(
        "\nReport saved:"
    )

    print(
        output_path
    )

    if not report[
        "all_readiness_checks_passed"
    ]:

        raise AssertionError(
            "Synthetic data usefulness "
            "evaluation did not pass "
            "all readiness checks."
        )

    print(
        "\nSYNTHETIC DATA USEFULNESS "
        "EVALUATION PASSED."
    )