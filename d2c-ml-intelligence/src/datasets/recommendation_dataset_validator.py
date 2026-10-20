import numpy as np
import pandas as pd

from src.datasets.recommendation_dataset import (
    RecommendationDatasetBuilder
)


class RecommendationDatasetValidator:

    def __init__(self):

        self.builder = (
            RecommendationDatasetBuilder()
        )

        self.dataset = (
            self.builder.build_dataset()
        )

        self.errors = []

    # ======================================================
    # MAIN
    # ======================================================

    def validate(self):

        self._validate_structure()
        self._validate_snapshot()
        self._validate_duplicates()
        self._validate_product_metadata()
        self._validate_non_negative_values()
        self._validate_temporal_consistency()
        self._validate_purchase_flags()
        self._validate_last_interaction()
        self._validate_interaction_scores()
        self._validate_pair_universe()
        self._validate_source_behavior_reconciliation()
        self._validate_source_order_reconciliation()
        self._validate_finite_values()

        return {
            "passed": len(self.errors) == 0,
            "error_count": len(self.errors),
            "errors": self.errors
        }

    # ======================================================
    # STRUCTURE
    # ======================================================

    def _validate_structure(self):

        required_columns = {
            "customer_id",
            "product_id",
            "snapshot_day",

            "product_view_count",
            "add_to_cart_count",
            "purchase_intent_count",
            "cart_abandonment_count",

            "purchase_count",
            "units_purchased",
            "purchase_value",
            "purchased_flag",

            "last_interaction_day",
            "days_since_last_interaction",

            "interaction_score",
            "interaction_score_log1p"
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

        if len(self.dataset) == 0:

            self.errors.append(
                "Recommendation dataset is empty."
            )

    # ======================================================
    # SNAPSHOT
    # ======================================================

    def _validate_snapshot(self):

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
                "Unexpected snapshot values: "
                f"{sorted(snapshots)}"
            )

    # ======================================================
    # DUPLICATES
    # ======================================================

    def _validate_duplicates(self):

        duplicates = (
            self.dataset
            .duplicated(
                subset=[
                    "customer_id",
                    "product_id"
                ]
            )
            .sum()
        )

        if duplicates > 0:

            self.errors.append(
                f"Found {duplicates} duplicate "
                "customer/product pairs."
            )

    # ======================================================
    # PRODUCT METADATA
    # ======================================================

    def _validate_product_metadata(self):

        metadata_columns = [
            "product_name",
            "category",
            "subcategory",
            "product_type",
            "price_band"
        ]

        missing = (
            self.dataset[
                metadata_columns
            ]
            .isna()
            .sum()
            .sum()
        )

        if missing > 0:

            self.errors.append(
                f"Found {missing} missing "
                "product metadata values."
            )

        known_products = set(
            self.builder.products[
                "product_id"
            ]
            .tolist()
        )

        dataset_products = set(
            self.dataset[
                "product_id"
            ]
            .tolist()
        )

        unknown = (
            dataset_products
            -
            known_products
        )

        if unknown:

            self.errors.append(
                "Unknown products found: "
                f"{sorted(unknown)}"
            )

    # ======================================================
    # NON-NEGATIVE VALUES
    # ======================================================

    def _validate_non_negative_values(self):

        columns = [
            "product_view_count",
            "add_to_cart_count",
            "purchase_intent_count",
            "cart_abandonment_count",
            "purchase_count",
            "units_purchased",
            "purchase_days",
            "purchase_value",
            "purchased_flag",
            "days_since_last_interaction",
            "interaction_score",
            "interaction_score_log1p"
        ]

        for column in columns:

            if (
                self.dataset[
                    column
                ] < 0
            ).any():

                self.errors.append(
                    f"Negative values found "
                    f"in {column}."
                )

    # ======================================================
    # TEMPORAL CONSISTENCY
    # ======================================================

    def _validate_temporal_consistency(self):

        timestamp_columns = [
            "last_behavior_day",
            "last_purchase_day",
            "last_interaction_day"
        ]

        for column in timestamp_columns:

            invalid = (
                self.dataset[
                    column
                ]
                .notna()
                &
                (
                    self.dataset[
                        column
                    ]
                    >
                    self.builder.snapshot_day
                )
            )

            if invalid.any():

                self.errors.append(
                    f"{column} contains "
                    "future information."
                )

        expected_recency = (
            self.builder.snapshot_day
            -
            self.dataset[
                "last_interaction_day"
            ]
        )

        actual_recency = (
            self.dataset[
                "days_since_last_interaction"
            ]
        )

        if not np.allclose(
            expected_recency,
            actual_recency,
            rtol=1e-6,
            atol=1e-6
        ):

            self.errors.append(
                "days_since_last_interaction "
                "does not reconcile."
            )

    # ======================================================
    # PURCHASE FLAGS
    # ======================================================

    def _validate_purchase_flags(self):

        expected = (
            self.dataset[
                "purchase_count"
            ]
            > 0
        ).astype(int)

        actual = (
            self.dataset[
                "purchased_flag"
            ]
        )

        if not (
            expected
            ==
            actual
        ).all():

            self.errors.append(
                "purchased_flag is inconsistent "
                "with purchase_count."
            )

        no_purchase = (
            self.dataset[
                "purchase_count"
            ]
            == 0
        )

        if (
            self.dataset.loc[
                no_purchase,
                "purchase_value"
            ]
            != 0
        ).any():

            self.errors.append(
                "Non-purchased pairs contain "
                "purchase value."
            )

        if (
            self.dataset.loc[
                no_purchase,
                "units_purchased"
            ]
            != 0
        ).any():

            self.errors.append(
                "Non-purchased pairs contain "
                "purchased units."
            )

    # ======================================================
    # LAST INTERACTION
    # ======================================================

    def _validate_last_interaction(self):

        expected = (
            self.dataset[
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

        actual = (
            self.dataset[
                "last_interaction_day"
            ]
        )

        if not np.allclose(
            expected,
            actual,
            rtol=1e-6,
            atol=1e-6,
            equal_nan=True
        ):

            self.errors.append(
                "last_interaction_day "
                "does not reconcile."
            )

        if actual.isna().any():

            self.errors.append(
                "Pairs without an interaction "
                "timestamp were found."
            )

    # ======================================================
    # INTERACTION SCORE
    # ======================================================

    def _validate_interaction_scores(self):

        weights = (
            self.builder.weights
        )

        expected_score = (
            self.dataset[
                "product_view_count"
            ]
            *
            weights[
                "product_view"
            ]
            +
            self.dataset[
                "add_to_cart_count"
            ]
            *
            weights[
                "add_to_cart"
            ]
            +
            self.dataset[
                "purchase_intent_count"
            ]
            *
            weights[
                "purchase_intent"
            ]
            +
            self.dataset[
                "cart_abandonment_count"
            ]
            *
            weights[
                "cart_abandonment"
            ]
            +
            self.dataset[
                "purchase_count"
            ]
            *
            weights[
                "purchase"
            ]
        )

        actual_score = (
            self.dataset[
                "interaction_score"
            ]
        )

        if not np.allclose(
            expected_score,
            actual_score,
            rtol=1e-6,
            atol=1e-6
        ):

            self.errors.append(
                "interaction_score does "
                "not match configured weights."
            )

        expected_log = np.log1p(
            actual_score
        )

        actual_log = (
            self.dataset[
                "interaction_score_log1p"
            ]
        )

        if not np.allclose(
            expected_log,
            actual_log,
            rtol=1e-6,
            atol=1e-6
        ):

            self.errors.append(
                "interaction_score_log1p "
                "does not reconcile."
            )

        if (
            actual_score <= 0
        ).any():

            self.errors.append(
                "Recommendation pairs with "
                "non-positive interaction "
                "scores were found."
            )

    # ======================================================
    # PAIR UNIVERSE
    # ======================================================

    def _validate_pair_universe(self):

        behavior = (
            self.builder.behavior[
                self.builder.behavior[
                    "simulation_day"
                ]
                <= self.builder.snapshot_day
            ]
        )

        orders = (
            self.builder.orders[
                self.builder.orders[
                    "simulation_day"
                ]
                <= self.builder.snapshot_day
            ]
        )

        behavior_pairs = set(
            zip(
                behavior[
                    "customer_id"
                ],
                behavior[
                    "product_id"
                ]
            )
        )

        order_pairs = set(
            zip(
                orders[
                    "customer_id"
                ],
                orders[
                    "product_id"
                ]
            )
        )

        expected_pairs = (
            behavior_pairs
            |
            order_pairs
        )

        actual_pairs = set(
            zip(
                self.dataset[
                    "customer_id"
                ],
                self.dataset[
                    "product_id"
                ]
            )
        )

        if actual_pairs != expected_pairs:

            missing = (
                expected_pairs
                -
                actual_pairs
            )

            extra = (
                actual_pairs
                -
                expected_pairs
            )

            self.errors.append(
                "Customer/product pair universe "
                "does not reconcile. "
                f"Missing={len(missing)}, "
                f"Extra={len(extra)}."
            )

    # ======================================================
    # SOURCE BEHAVIOR RECONCILIATION
    # ======================================================

    def _validate_source_behavior_reconciliation(
        self
    ):

        behavior = (
            self.builder.behavior[
                self.builder.behavior[
                    "simulation_day"
                ]
                <= self.builder.snapshot_day
            ]
        )

        expected_total = (
            len(
                behavior
            )
        )

        actual_total = (
            self.dataset[
                "product_view_count"
            ].sum()
            +
            self.dataset[
                "add_to_cart_count"
            ].sum()
            +
            self.dataset[
                "purchase_intent_count"
            ].sum()
            +
            self.dataset[
                "cart_abandonment_count"
            ].sum()
        )

        if actual_total != expected_total:

            self.errors.append(
                "Behavior signal total "
                f"{actual_total} does not match "
                f"source total {expected_total}."
            )

    # ======================================================
    # SOURCE ORDER RECONCILIATION
    # ======================================================

    def _validate_source_order_reconciliation(
        self
    ):

        orders = (
            self.builder.orders[
                self.builder.orders[
                    "simulation_day"
                ]
                <= self.builder.snapshot_day
            ]
        )

        expected_count = (
            len(
                orders
            )
        )

        actual_count = (
            self.dataset[
                "purchase_count"
            ]
            .sum()
        )

        if actual_count != expected_count:

            self.errors.append(
                "Purchase count "
                f"{actual_count} does not match "
                f"source order count "
                f"{expected_count}."
            )

        expected_units = (
            orders[
                "quantity"
            ]
            .sum()
        )

        actual_units = (
            self.dataset[
                "units_purchased"
            ]
            .sum()
        )

        if actual_units != expected_units:

            self.errors.append(
                "Purchased units do not "
                "match source orders."
            )

        expected_value = (
            orders[
                "gross_amount"
            ]
            .sum()
        )

        actual_value = (
            self.dataset[
                "purchase_value"
            ]
            .sum()
        )

        if not np.isclose(
            expected_value,
            actual_value,
            rtol=1e-6,
            atol=1e-6
        ):

            self.errors.append(
                "Purchase value "
                f"{actual_value} does not match "
                f"source revenue "
                f"{expected_value}."
            )

    # ======================================================
    # FINITE VALUES
    # ======================================================

    def _validate_finite_values(self):

        columns = [
            "product_view_count",
            "add_to_cart_count",
            "purchase_intent_count",
            "cart_abandonment_count",
            "purchase_count",
            "units_purchased",
            "purchase_days",
            "purchase_value",
            "days_since_last_interaction",
            "interaction_score",
            "interaction_score_log1p"
        ]

        values = (
            self.dataset[
                columns
            ]
            .to_numpy(
                dtype=float
            )
        )

        if not np.isfinite(
            values
        ).all():

            self.errors.append(
                "NaN or infinite numeric "
                "interaction values found."
            )


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 70)
    print(
        "PHASE 7 - RECOMMENDATION DATASET VALIDATION"
    )
    print("=" * 70)

    validator = (
        RecommendationDatasetValidator()
    )

    result = (
        validator.validate()
    )

    print(
        f"\nInteraction rows validated: "
        f"{len(validator.dataset):,}"
    )

    print(
        "\nUnique customers:"
    )

    print(
        validator.dataset[
            "customer_id"
        ]
        .nunique()
    )

    print(
        "\nUnique products:"
    )

    print(
        validator.dataset[
            "product_id"
        ]
        .nunique()
    )

    print(
        "\nPurchase reconciliation:"
    )

    print(
        int(
            validator.dataset[
                "purchase_count"
            ]
            .sum()
        )
    )

    print(
        "\nBehavior reconciliation:"
    )

    behavior_total = (
        validator.dataset[
            "product_view_count"
        ].sum()
        +
        validator.dataset[
            "add_to_cart_count"
        ].sum()
        +
        validator.dataset[
            "purchase_intent_count"
        ].sum()
        +
        validator.dataset[
            "cart_abandonment_count"
        ].sum()
    )

    print(
        int(
            behavior_total
        )
    )

    print(
        "\nValidation result:"
    )

    print(result)

    if not result[
        "passed"
    ]:

        raise AssertionError(
            "Recommendation dataset "
            "validation failed."
        )

    print(
        "\nRECOMMENDATION DATASET "
        "VALIDATION PASSED."
    )
    