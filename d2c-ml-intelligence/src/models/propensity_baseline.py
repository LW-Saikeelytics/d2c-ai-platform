from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression

from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score
)

from sklearn.pipeline import Pipeline

from sklearn.preprocessing import (
    OneHotEncoder,
    StandardScaler
)

from src.datasets.propensity_dataset import (
    PropensityDatasetBuilder
)


class PropensityBaselineModel:

    def __init__(self):

        self.dataset_builder = (
            PropensityDatasetBuilder()
        )

        self.dataset = (
            self.dataset_builder
            .build_dataset()
        )

        self.train_day = 30
        self.validation_day = 45
        self.test_day = 60

        self.target_column = (
            "purchase_propensity_label"
        )

        # Generator-authored / identifiers /
        # absolute time anchors excluded.
        self.excluded_columns = {
            "customer_id",
            "snapshot_day",
            "purchase_propensity_label",

            "segment",
            "price_tendency",
            "discount_sensitivity",
            "premium_product_tendency",
            "repeat_purchase_tendency",

            "registration_day",

            "hist_last_activity_day",
            "last_7d_last_activity_day",
            "last_30d_last_activity_day",

            "hist_last_order_day"
        }

        self.feature_columns = [
            column
            for column
            in self.dataset.columns
            if column not in self.excluded_columns
        ]

        self.pipeline = None

    # ======================================================
    # SPLIT
    # ======================================================

    def _get_split(
        self,
        snapshot_day
    ):

        split = (
            self.dataset[
                self.dataset[
                    "snapshot_day"
                ]
                == snapshot_day
            ]
            .copy()
        )

        X = (
            split[
                self.feature_columns
            ]
        )

        y = (
            split[
                self.target_column
            ]
            .astype(int)
        )

        return X, y

    # ======================================================
    # PIPELINE
    # ======================================================

    def _build_pipeline(
        self,
        X_train
    ):

        categorical_columns = (
            X_train
            .select_dtypes(
                include=[
                    "object",
                    "category"
                ]
            )
            .columns
            .tolist()
        )

        numeric_columns = [
            column
            for column
            in X_train.columns
            if column not in categorical_columns
        ]

        numeric_pipeline = (
            Pipeline(
                steps=[
                    (
                        "imputer",
                        SimpleImputer(
                            strategy="median"
                        )
                    ),
                    (
                        "scaler",
                        StandardScaler()
                    )
                ]
            )
        )

        categorical_pipeline = (
            Pipeline(
                steps=[
                    (
                        "imputer",
                        SimpleImputer(
                            strategy="most_frequent"
                        )
                    ),
                    (
                        "encoder",
                        OneHotEncoder(
                            handle_unknown="ignore"
                        )
                    )
                ]
            )
        )

        preprocessor = (
            ColumnTransformer(
                transformers=[
                    (
                        "numeric",
                        numeric_pipeline,
                        numeric_columns
                    ),
                    (
                        "categorical",
                        categorical_pipeline,
                        categorical_columns
                    )
                ]
            )
        )

        model = (
            LogisticRegression(
                class_weight="balanced",
                max_iter=2000,
                random_state=42
            )
        )

        self.pipeline = (
            Pipeline(
                steps=[
                    (
                        "preprocessor",
                        preprocessor
                    ),
                    (
                        "model",
                        model
                    )
                ]
            )
        )

        return {
            "numeric_columns":
                len(
                    numeric_columns
                ),

            "categorical_columns":
                len(
                    categorical_columns
                )
        }

    # ======================================================
    # TRAIN
    # ======================================================

    def train(self):

        X_train, y_train = (
            self._get_split(
                self.train_day
            )
        )

        column_summary = (
            self._build_pipeline(
                X_train
            )
        )

        self.pipeline.fit(
            X_train,
            y_train
        )

        return {
            "train_rows":
                len(X_train),

            "positive_rows":
                int(
                    y_train.sum()
                ),

            "positive_rate":
                float(
                    y_train.mean()
                ),

            "feature_columns":
                len(
                    self.feature_columns
                ),

            **column_summary
        }

    # ======================================================
    # EVALUATE
    # ======================================================

    def evaluate(
        self,
        snapshot_day
    ):

        X, y = (
            self._get_split(
                snapshot_day
            )
        )

        probabilities = (
            self.pipeline
            .predict_proba(
                X
            )[:, 1]
        )

        predictions = (
            probabilities >= 0.5
        ).astype(int)

        matrix = (
            confusion_matrix(
                y,
                predictions
            )
        )

        return {
            "snapshot_day":
                snapshot_day,

            "rows":
                len(X),

            "actual_purchase_rate":
                float(
                    y.mean()
                ),

            "predicted_purchase_rate":
                float(
                    predictions.mean()
                ),

            "accuracy":
                accuracy_score(
                    y,
                    predictions
                ),

            "precision":
                precision_score(
                    y,
                    predictions,
                    zero_division=0
                ),

            "recall":
                recall_score(
                    y,
                    predictions,
                    zero_division=0
                ),

            "f1":
                f1_score(
                    y,
                    predictions,
                    zero_division=0
                ),

            "roc_auc":
                roc_auc_score(
                    y,
                    probabilities
                ),

            "pr_auc":
                average_precision_score(
                    y,
                    probabilities
                ),

            "confusion_matrix":
                matrix.tolist()
        }


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 70)
    print(
        "PHASE 7 - PURCHASE PROPENSITY BASELINE MODEL"
    )
    print("=" * 70)

    baseline = (
        PropensityBaselineModel()
    )

    training = (
        baseline.train()
    )

    print(
        "\nTemporal split:"
    )

    print(
        "Train      : Day 30 "
        "(target Days 31-60)"
    )

    print(
        "Diagnostic : Day 45 "
        "(target Days 46-75)"
    )

    print(
        "Test       : Day 60 "
        "(target Days 61-90)"
    )

    print(
        "\nTraining configuration:"
    )

    print(training)

    print(
        "\nTRAIN PERFORMANCE"
    )

    print(
        baseline.evaluate(
            baseline.train_day
        )
    )

    print(
        "\nDAY-45 DIAGNOSTIC PERFORMANCE"
    )

    print(
        baseline.evaluate(
            baseline.validation_day
        )
    )

    print(
        "\nDAY-60 FINAL TEST PERFORMANCE"
    )

    print(
        baseline.evaluate(
            baseline.test_day
        )
    )

    print(
        "\nPURCHASE PROPENSITY "
        "BASELINE MODEL TEST PASSED."
    )