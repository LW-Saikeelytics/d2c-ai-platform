class DatasetQualityReport:

    def __init__(
        self,
        dataset_quality_result,
        business_rule_result,
        statistical_result,
        analytics_validation,
        daily_analytics
    ):
        self.dataset_quality_result = dataset_quality_result
        self.business_rule_result = business_rule_result
        self.statistical_result = statistical_result
        self.analytics_validation = analytics_validation
        self.daily_analytics = daily_analytics

    # ============================================================
    # BUILD CONSOLIDATED REPORT
    # ============================================================

    def build(self):

        errors = []
        warnings = []

        # --------------------------------------------------------
        # COLLECT ERRORS
        # --------------------------------------------------------

        errors.extend(
            self.dataset_quality_result.get("errors", [])
        )

        errors.extend(
            self.business_rule_result.get("errors", [])
        )

        errors.extend(
            self.statistical_result.get("errors", [])
        )

        errors.extend(
            self.analytics_validation.get("errors", [])
        )

        # --------------------------------------------------------
        # COLLECT WARNINGS
        # --------------------------------------------------------

        warnings.extend(
            self.dataset_quality_result.get("warnings", [])
        )

        warnings.extend(
            self.business_rule_result.get("warnings", [])
        )

        warnings.extend(
            self.statistical_result.get("warnings", [])
        )

        # --------------------------------------------------------
        # OVERALL STATUS
        # --------------------------------------------------------

        passed = len(errors) == 0

        # --------------------------------------------------------
        # REPORT
        # --------------------------------------------------------

        return {
            "passed": passed,

            "error_count": len(errors),
            "warning_count": len(warnings),

            "errors": errors,
            "warnings": warnings,

            "layers": {
                "dataset_quality": {
                    "passed": self.dataset_quality_result.get(
                        "passed",
                        False
                    ),
                    "checks": self.dataset_quality_result.get(
                        "checks",
                        {}
                    )
                },

                "business_rules": {
                    "passed": self.business_rule_result.get(
                        "passed",
                        False
                    ),
                    "checks": self.business_rule_result.get(
                        "checks",
                        {}
                    )
                },

                "statistical_quality": {
                    "passed": self.statistical_result.get(
                        "passed",
                        False
                    ),
                    "checks": self.statistical_result.get(
                        "checks",
                        {}
                    )
                },

                "analytics_reconciliation": {
                    "passed": self.analytics_validation.get(
                        "passed",
                        False
                    ),
                    "totals": self.analytics_validation.get(
                        "totals",
                        {}
                    )
                }
            },

            "daily_analytics": self.daily_analytics
        }


    # ============================================================
    # BUILD COMPACT SUMMARY
    # ============================================================

    def build_summary(self):

        report = self.build()

        statistical_checks = (
            self.statistical_result
            .get("checks", {})
        )

        core_statistics = statistical_checks.get(
            "core_statistics",
            {}
        )

        anomaly_statistics = statistical_checks.get(
            "statistical_anomalies",
            {}
        )

        analytics_totals = self.analytics_validation.get(
            "totals",
            {}
        )

        return {
            "status": (
                "PASS"
                if report["passed"]
                else "FAIL"
            ),

            "error_count": report["error_count"],
            "warning_count": report["warning_count"],

            "layers": {
                "dataset_quality": (
                    "PASS"
                    if self.dataset_quality_result.get("passed")
                    else "FAIL"
                ),

                "business_rules": (
                    "PASS"
                    if self.business_rule_result.get("passed")
                    else "FAIL"
                ),

                "statistical_quality": (
                    "PASS"
                    if self.statistical_result.get("passed")
                    else "FAIL"
                ),

                "analytics_reconciliation": (
                    "PASS"
                    if self.analytics_validation.get("passed")
                    else "FAIL"
                )
            },

            "dataset": {
                "customers": core_statistics.get(
                    "customer_count",
                    0
                ),
                "orders": analytics_totals.get(
                    "orders",
                    0
                ),
                "events": analytics_totals.get(
                    "events",
                    0
                ),
                "revenue": analytics_totals.get(
                    "revenue",
                    0.0
                )
            },

            "business_metrics": {
                "average_order_value": core_statistics.get(
                    "average_order_value",
                    0.0
                ),
                "customer_conversion_rate": core_statistics.get(
                    "customer_conversion_rate",
                    0.0
                ),
                "orders_per_customer": core_statistics.get(
                    "orders_per_customer",
                    0.0
                ),
                "events_per_customer": core_statistics.get(
                    "events_per_customer",
                    0.0
                )
            },

            "anomalies": {
                "count": anomaly_statistics.get(
                    "anomaly_count",
                    0
                ),
                "small_sample": anomaly_statistics.get(
                    "small_sample",
                    False
                )
            },

            "warnings": report["warnings"]
        }