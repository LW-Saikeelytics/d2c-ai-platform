import numpy as np

from sklearn.compose import (
    ColumnTransformer
)

from sklearn.ensemble import (
    RandomForestRegressor
)

from sklearn.impute import (
    SimpleImputer
)

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)

from sklearn.pipeline import (
    Pipeline
)

from sklearn.preprocessing import (
    OneHotEncoder
)

from src.datasets.clv_dataset import (
    CLVDatasetBuilder
)


class CLVBaselineModel:

    def __init__(self):

        self.dataset_builder = (
            CLVDatasetBuilder()
        )

        self.dataset = (
            self.dataset_builder
            .build_dataset()
        )

        # --------------------------------------------------
        # TEMPORAL SPLIT
        # --------------------------------------------------

        self.train_day = 30
        self.validation_day = 45
        self.test_day = 60

        self.target_column = (
            "future_customer_value_30d"
        )

        # --------------------------------------------------
        # EXCLUDED COLUMNS
        #
        # Remove:
        # - identifiers
        # - target
        # - generator-authored latent traits
        # - absolute time anchors
        # --------------------------------------------------

        self.excluded_columns = {
            "customer_id",
            "snapshot_day",
            "future_customer_value_30d",

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
            if column not in (
                self.excluded_columns
            )
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
            .astype(float)
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
            if column not in (
                categorical_columns
            )
        ]

        numeric_pipeline = (
            Pipeline(
                steps=[
                    (
                        "imputer",
                        SimpleImputer(
                            strategy="median"
                        )
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
            RandomForestRegressor(
                n_estimators=200,
                max_depth=12,
                min_samples_leaf=5,
                random_state=42,
                n_jobs=-1
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

            "positive_value_rows":
                int(
                    (
                        y_train > 0
                    ).sum()
                ),

            "positive_value_rate":
                float(
                    (
                        y_train > 0
                    ).mean()
                ),

            "mean_target_value":
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

        predictions = (
            self.pipeline.predict(
                X
            )
        )

        # Revenue cannot be negative.
        predictions = np.maximum(
            predictions,
            0.0
        )

        mae = (
            mean_absolute_error(
                y,
                predictions
            )
        )

        rmse = np.sqrt(
            mean_squared_error(
                y,
                predictions
            )
        )

        r2 = (
            r2_score(
                y,
                predictions
            )
        )

        positive_mask = (
            y > 0
        )

        if positive_mask.any():

            positive_mae = (
                mean_absolute_error(
                    y[
                        positive_mask
                    ],
                    predictions[
                        positive_mask
                    ]
                )
            )

        else:

            positive_mae = np.nan

        # --------------------------------------------------
        # ZERO-PREDICTION REFERENCE
        #
        # Because CLV is highly sparse, always predicting
        # zero is an important reference point.
        # --------------------------------------------------

        zero_predictions = (
            np.zeros(
                len(y)
            )
        )

        zero_baseline_mae = (
            mean_absolute_error(
                y,
                zero_predictions
            )
        )

        zero_baseline_rmse = np.sqrt(
            mean_squared_error(
                y,
                zero_predictions
            )
        )

        return {
            "snapshot_day":
                snapshot_day,

            "rows":
                len(X),

            "positive_value_rate":
                float(
                    positive_mask.mean()
                ),

            "actual_mean_value":
                float(
                    y.mean()
                ),

            "predicted_mean_value":
                float(
                    predictions.mean()
                ),

            "mae":
                float(
                    mae
                ),

            "rmse":
                float(
                    rmse
                ),

            "r2":
                float(
                    r2
                ),

            "positive_customer_mae":
                float(
                    positive_mae
                ),

            "zero_baseline_mae":
                float(
                    zero_baseline_mae
                ),

            "zero_baseline_rmse":
                float(
                    zero_baseline_rmse
                ),

            "mae_improvement_vs_zero":
                float(
                    zero_baseline_mae
                    -
                    mae
                )
        }


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 70)
    print(
        "PHASE 7 - CLV REGRESSION BASELINE MODEL"
    )
    print("=" * 70)

    baseline = (
        CLVBaselineModel()
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
        "\nCLV REGRESSION "
        "BASELINE MODEL TEST PASSED."
    )