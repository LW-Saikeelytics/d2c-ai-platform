import numpy as np
import pandas as pd

from src.datasets.segmentation_dataset import (
    SegmentationDatasetBuilder
)


class SegmentationDatasetValidator:

    def __init__(self):

        self.builder = (
            SegmentationDatasetBuilder()
        )

        self.dataset = (
            self.builder.build_dataset()
        )

        self.feature_columns = (
            self.builder.get_feature_columns()
        )

        self.errors = []

    # ======================================================
    # MAIN
    # ======================================================

    def validate(self):

        self._validate_structure()
        self._validate_single_snapshot()
        self._validate_duplicates()
        self._validate_missing_values()
        self._validate_numeric_features()
        self._validate_finite_values()
        self._validate_forbidden_columns()
        self._validate_non_negative_features()
        self._validate_purchase_consistency()
        self._validate_behavior_consistency()
        self._validate_conversion_consistency()
        self._validate_activity_flags()
        self._validate_feature_variance()

        return {
            "passed": len(self.errors) == 0,
            "error_count": len(self.errors),
            "errors": self.errors
        }

    # ======================================================
    # STRUCTURE
    # ======================================================

    def _validate_structure(self):

        expected_rows = 10000

        if len(self.dataset) != expected_rows:

            self.errors.append(
                f"Expected {expected_rows} rows, "
                f"found {len(self.dataset)}."
            )

        required_columns = {
            "customer_id",
            "snapshot_day"
        }

        missing = (
            required_columns
            -
            set(
                self.dataset.columns
            )
        )

        if missing:

            self.errors.append(
                "Missing required columns: "
                f"{sorted(missing)}"
            )

        if len(self.feature_columns) == 0:

            self.errors.append(
                "No clustering features found."
            )

    # ======================================================
    # SNAPSHOT
    # ======================================================

    def _validate_single_snapshot(self):

        snapshots = set(
            self.dataset[
                "snapshot_day"
            ]
            .unique()
            .tolist()
        )

        expected = {
            self.builder.snapshot_day
        }

        if snapshots != expected:

            self.errors.append(
                "Unexpected segmentation snapshots: "
                f"{sorted(snapshots)}"
            )

    # ======================================================
    # DUPLICATES
    # ======================================================

    def _validate_duplicates(self):

        duplicates = (
            self.dataset[
                "customer_id"
            ]
            .duplicated()
            .sum()
        )

        if duplicates > 0:

            self.errors.append(
                f"Found {duplicates} duplicate "
                "customers."
            )

        unique_customers = (
            self.dataset[
                "customer_id"
            ]
            .nunique()
        )

        if unique_customers != len(
            self.dataset
        ):

            self.errors.append(
                "Customer IDs are not unique."
            )

    # ======================================================
    # MISSING VALUES
    # ======================================================

    def _validate_missing_values(self):

        missing_count = (
            self.dataset[
                self.feature_columns
            ]
            .isna()
            .sum()
            .sum()
        )

        if missing_count > 0:

            self.errors.append(
                f"Found {missing_count} missing "
                "clustering feature values."
            )

    # ======================================================
    # NUMERIC FEATURES
    # ======================================================

    def _validate_numeric_features(self):

        non_numeric = [
            column
            for column
            in self.feature_columns
            if not pd.api.types.is_numeric_dtype(
                self.dataset[
                    column
                ]
            )
        ]

        if non_numeric:

            self.errors.append(
                "Non-numeric clustering features "
                f"found: {non_numeric}"
            )

    # ======================================================
    # FINITE VALUES
    # ======================================================

    def _validate_finite_values(self):

        values = (
            self.dataset[
                self.feature_columns
            ]
            .to_numpy(
                dtype=float
            )
        )

        if not np.isfinite(
            values
        ).all():

            self.errors.append(
                "NaN or infinite values found "
                "in clustering features."
            )

    # ======================================================
    # FORBIDDEN / GENERATOR-AUTHORED FEATURES
    # ======================================================

    def _validate_forbidden_columns(self):

        forbidden_columns = {
            "segment",
            "behavior_profile",
            "purchase_propensity",
            "price_tendency",
            "discount_sensitivity",
            "premium_product_tendency",
            "repeat_purchase_tendency",
            "status",
            "lifetime_orders",
            "lifetime_spend",
            "last_order_day",
            "conversion_probability",

            "churn_label",
            "purchase_propensity_label",
            "future_customer_value_30d",
            "future_value_positive"
        }

        leaked = (
            forbidden_columns
            &
            set(
                self.feature_columns
            )
        )

        if leaked:

            self.errors.append(
                "Forbidden clustering features "
                f"found: {sorted(leaked)}"
            )

    # ======================================================
    # NON-NEGATIVE FEATURES
    # ======================================================

    def _validate_non_negative_features(self):

        # Conversion-rate change may legitimately
        # be negative because recent performance
        # can decline relative to the 30-day rate.
        excluded = {
            "conversion_rate_change_7d_vs_30d"
        }

        for column in (
            self.feature_columns
        ):

            if column in excluded:
                continue

            values = (
                self.dataset[
                    column
                ]
            )

            if (
                values < 0
            ).any():

                self.errors.append(
                    f"Negative values found "
                    f"in {column}."
                )

    # ======================================================
    # PURCHASE CONSISTENCY
    # ======================================================

    def _validate_purchase_consistency(self):

        expected_flag = (
            self.dataset[
                "hist_order_count"
            ]
            > 0
        ).astype(int)

        actual_flag = (
            self.dataset[
                "has_purchase_history"
            ]
        )

        if not (
            expected_flag
            ==
            actual_flag
        ).all():

            self.errors.append(
                "has_purchase_history is "
                "inconsistent with "
                "hist_order_count."
            )

        no_purchase = (
            self.dataset[
                "hist_order_count"
            ]
            == 0
        )

        if (
            self.dataset.loc[
                no_purchase,
                "hist_total_spend"
            ]
            != 0
        ).any():

            self.errors.append(
                "Customers with zero orders "
                "have non-zero historical spend."
            )

        if (
            self.dataset.loc[
                no_purchase,
                "hist_average_order_value"
            ]
            != 0
        ).any():

            self.errors.append(
                "Customers with zero orders "
                "have non-zero historical AOV."
            )

    # ======================================================
    # BEHAVIOR CONSISTENCY
    # ======================================================

    def _validate_behavior_consistency(self):

        expected_flag = (
            self.dataset[
                "hist_total_events"
            ]
            > 0
        ).astype(int)

        actual_flag = (
            self.dataset[
                "has_behavior_history"
            ]
        )

        if not (
            expected_flag
            ==
            actual_flag
        ).all():

            self.errors.append(
                "has_behavior_history is "
                "inconsistent with "
                "hist_total_events."
            )

        if (
            self.dataset[
                "last_7d_total_events"
            ]
            >
            self.dataset[
                "last_30d_total_events"
            ]
        ).any():

            self.errors.append(
                "last_7d_total_events exceeds "
                "last_30d_total_events."
            )

        if (
            self.dataset[
                "last_30d_total_events"
            ]
            >
            self.dataset[
                "hist_total_events"
            ]
        ).any():

            self.errors.append(
                "last_30d_total_events exceeds "
                "historical total events."
            )

    # ======================================================
    # CONVERSION CONSISTENCY
    # ======================================================

    def _validate_conversion_consistency(self):

        expected_flag = (
            self.dataset[
                "hist_converted_days"
            ]
            > 0
        ).astype(int)

        actual_flag = (
            self.dataset[
                "has_historical_conversion"
            ]
        )

        if not (
            expected_flag
            ==
            actual_flag
        ).all():

            self.errors.append(
                "has_historical_conversion is "
                "inconsistent with "
                "hist_converted_days."
            )

        if (
            self.dataset[
                "hist_converted_days"
            ]
            >
            self.dataset[
                "hist_evaluated_days"
            ]
        ).any():

            self.errors.append(
                "Historical converted days "
                "exceed evaluated days."
            )

        if (
            self.dataset[
                "hist_nonconverted_days"
            ]
            +
            self.dataset[
                "hist_converted_days"
            ]
            !=
            self.dataset[
                "hist_evaluated_days"
            ]
        ).any():

            self.errors.append(
                "Historical conversion-day "
                "accounting does not reconcile."
            )

    # ======================================================
    # ACTIVITY FLAGS
    # ======================================================

    def _validate_activity_flags(self):

        expected_7d = (
            self.dataset[
                "last_7d_total_events"
            ]
            > 0
        ).astype(int)

        if not (
            expected_7d
            ==
            self.dataset[
                "active_in_last_7d"
            ]
        ).all():

            self.errors.append(
                "active_in_last_7d "
                "is inconsistent."
            )

        expected_30d = (
            self.dataset[
                "last_30d_total_events"
            ]
            > 0
        ).astype(int)

        if not (
            expected_30d
            ==
            self.dataset[
                "active_in_last_30d"
            ]
        ).all():

            self.errors.append(
                "active_in_last_30d "
                "is inconsistent."
            )

    # ======================================================
    # FEATURE VARIANCE
    # ======================================================

    def _validate_feature_variance(self):

        zero_variance = [
            column
            for column
            in self.feature_columns
            if (
                self.dataset[
                    column
                ]
                .nunique(
                    dropna=False
                )
                <= 1
            )
        ]

        if zero_variance:

            self.errors.append(
                "Zero-variance clustering "
                f"features found: {zero_variance}"
            )


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 70)
    print(
        "PHASE 7 - SEGMENTATION DATASET VALIDATION"
    )
    print("=" * 70)

    validator = (
        SegmentationDatasetValidator()
    )

    result = (
        validator.validate()
    )

    print(
        f"\nRows validated: "
        f"{len(validator.dataset):,}"
    )

    print(
        f"Clustering features validated: "
        f"{len(validator.feature_columns)}"
    )

    print(
        "\nBehavior-history customers:"
    )

    print(
        int(
            validator.dataset[
                "has_behavior_history"
            ]
            .sum()
        )
    )

    print(
        "\nPurchase-history customers:"
    )

    print(
        int(
            validator.dataset[
                "has_purchase_history"
            ]
            .sum()
        )
    )

    zero_variance = [
        column
        for column
        in validator.feature_columns
        if (
            validator.dataset[
                column
            ]
            .nunique(
                dropna=False
            )
            <= 1
        )
    ]

    print(
        "\nZero-variance features:"
    )

    print(
        zero_variance
    )

    print(
        "\nValidation result:"
    )

    print(result)

    if not result[
        "passed"
    ]:

        raise AssertionError(
            "Segmentation dataset "
            "validation failed."
        )

    print(
        "\nSEGMENTATION DATASET "
        "VALIDATION PASSED."
    )