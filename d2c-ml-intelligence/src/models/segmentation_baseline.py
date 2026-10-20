import pandas as pd

from sklearn.cluster import KMeans

from sklearn.metrics import (
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score
)

from sklearn.preprocessing import (
    StandardScaler
)

from src.datasets.segmentation_dataset import (
    SegmentationDatasetBuilder
)


class SegmentationBaselineModel:

    def __init__(self):

        self.dataset_builder = (
            SegmentationDatasetBuilder()
        )

        self.dataset = (
            self.dataset_builder
            .build_dataset()
        )

        self.feature_columns = (
            self.dataset_builder
            .get_feature_columns()
        )

        model_config = (
            self.dataset_builder.config[
                "baseline_models"
            ][
                "segmentation"
            ]
        )

        self.candidate_clusters = (
            model_config[
                "candidate_clusters"
            ]
        )

        self.silhouette_sample_size = (
            model_config[
                "silhouette_sample_size"
            ]
        )

        self.random_state = (
            model_config[
                "random_state"
            ]
        )

        self.scaler = (
            StandardScaler()
        )

        self.scaled_features = None
        self.results = None

        self.best_k = None
        self.best_model = None
        self.clustered_dataset = None

    # ======================================================
    # PREPARE FEATURES
    # ======================================================

    def prepare_features(self):

        X = (
            self.dataset[
                self.feature_columns
            ]
            .copy()
        )

        self.scaled_features = (
            self.scaler.fit_transform(
                X
            )
        )

        return {
            "rows":
                len(X),

            "features":
                len(
                    self.feature_columns
                )
        }

    # ======================================================
    # TEST CLUSTER COUNTS
    # ======================================================

    def evaluate_cluster_counts(self):

        if self.scaled_features is None:

            self.prepare_features()

        results = []

        sample_size = min(
            self.silhouette_sample_size,
            len(
                self.dataset
            )
        )

        for k in (
            self.candidate_clusters
        ):

            model = (
                KMeans(
                    n_clusters=k,
                    n_init=10,
                    random_state=(
                        self.random_state
                    )
                )
            )

            labels = (
                model.fit_predict(
                    self.scaled_features
                )
            )

            silhouette = (
                silhouette_score(
                    self.scaled_features,
                    labels,
                    sample_size=sample_size,
                    random_state=(
                        self.random_state
                    )
                )
            )

            davies_bouldin = (
                davies_bouldin_score(
                    self.scaled_features,
                    labels
                )
            )

            calinski_harabasz = (
                calinski_harabasz_score(
                    self.scaled_features,
                    labels
                )
            )

            cluster_sizes = (
                pd.Series(
                    labels
                )
                .value_counts()
            )

            results.append(
                {
                    "k":
                        k,

                    "silhouette_score":
                        float(
                            silhouette
                        ),

                    "davies_bouldin_score":
                        float(
                            davies_bouldin
                        ),

                    "calinski_harabasz_score":
                        float(
                            calinski_harabasz
                        ),

                    "smallest_cluster":
                        int(
                            cluster_sizes.min()
                        ),

                    "largest_cluster":
                        int(
                            cluster_sizes.max()
                        )
                }
            )

        self.results = (
            pd.DataFrame(
                results
            )
            .sort_values(
                "k"
            )
            .reset_index(
                drop=True
            )
        )

        return self.results

    # ======================================================
    # SELECT BEST K
    # ======================================================

    def select_best_k(self):

        if self.results is None:

            self.evaluate_cluster_counts()

        best_row = (
            self.results
            .sort_values(
                [
                    "silhouette_score",
                    "davies_bouldin_score"
                ],
                ascending=[
                    False,
                    True
                ]
            )
            .iloc[0]
        )

        self.best_k = int(
            best_row[
                "k"
            ]
        )

        return self.best_k

    # ======================================================
    # FIT FINAL BASELINE
    # ======================================================

    def fit_best_model(self):

        if self.scaled_features is None:

            self.prepare_features()

        if self.best_k is None:

            self.select_best_k()

        self.best_model = (
            KMeans(
                n_clusters=(
                    self.best_k
                ),
                n_init=10,
                random_state=(
                    self.random_state
                )
            )
        )

        labels = (
            self.best_model.fit_predict(
                self.scaled_features
            )
        )

        self.clustered_dataset = (
            self.dataset.copy()
        )

        self.clustered_dataset[
            "cluster_id"
        ] = labels

        return self.clustered_dataset

    # ======================================================
    # CLUSTER SIZES
    # ======================================================

    def get_cluster_sizes(self):

        if self.clustered_dataset is None:

            self.fit_best_model()

        sizes = (
            self.clustered_dataset[
                "cluster_id"
            ]
            .value_counts()
            .sort_index()
            .rename(
                "customers"
            )
            .to_frame()
        )

        sizes[
            "customer_share"
        ] = (
            sizes[
                "customers"
            ]
            /
            len(
                self.clustered_dataset
            )
        )

        return sizes

    # ======================================================
    # BUSINESS PROFILE
    # ======================================================

    def get_cluster_profiles(self):

        if self.clustered_dataset is None:

            self.fit_best_model()

        profile_columns = [
            "hist_total_events",
            "hist_active_days",

            "last_30d_total_events",
            "last_7d_total_events",

            "days_since_last_behavior",

            "hist_order_count",
            "hist_total_spend",
            "hist_average_order_value",

            "days_since_last_order",

            "has_purchase_history",

            "hist_conversion_rate",
            "has_historical_conversion",

            "active_in_last_7d",
            "active_in_last_30d"
        ]

        profiles = (
            self.clustered_dataset
            .groupby(
                "cluster_id"
            )[
                profile_columns
            ]
            .mean()
            .round(4)
        )

        return profiles

    # ======================================================
    # CLUSTER CENTERS IN ORIGINAL SCALE
    # ======================================================

    def get_cluster_centers(self):

        if self.best_model is None:

            self.fit_best_model()

        centers_original = (
            self.scaler
            .inverse_transform(
                self.best_model
                .cluster_centers_
            )
        )

        return pd.DataFrame(
            centers_original,
            columns=(
                self.feature_columns
            )
        ).assign(
            cluster_id=range(
                self.best_k
            )
        )


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 70)

    print(
        "PHASE 7 - CUSTOMER "
        "SEGMENTATION BASELINE MODEL"
    )

    print("=" * 70)

    baseline = (
        SegmentationBaselineModel()
    )

    preparation = (
        baseline.prepare_features()
    )

    print(
        "\nDataset:"
    )

    print(preparation)

    print(
        "\nCandidate cluster evaluation:"
    )

    results = (
        baseline
        .evaluate_cluster_counts()
    )

    print(
        results.to_string(
            index=False
        )
    )

    best_k = (
        baseline.select_best_k()
    )

    print(
        f"\nSelected baseline k: "
        f"{best_k}"
    )

    baseline.fit_best_model()

    print(
        "\nCluster sizes:"
    )

    print(
        baseline
        .get_cluster_sizes()
    )

    print(
        "\nCluster business profiles:"
    )

    print(
        baseline
        .get_cluster_profiles()
        .to_string()
    )

    print(
        "\nCUSTOMER SEGMENTATION "
        "BASELINE MODEL TEST PASSED."
    )