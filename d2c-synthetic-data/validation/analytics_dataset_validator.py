import csv
from pathlib import Path


class AnalyticsDatasetValidator:

    def __init__(
        self,
        state,
        config,
        analytics_tables,
        analytics_export_result
    ):
        self.state = state
        self.config = config
        self.analytics_tables = analytics_tables
        self.analytics_export_result = (
            analytics_export_result
        )

        self.errors = []
        self.checks = {}

    # ---------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------

    def _record_check(
        self,
        name,
        passed,
        message=None
    ):
        self.checks[name] = passed

        if not passed:
            self.errors.append(
                message or name
            )

    # ---------------------------------------------------------
    # REQUIRED TABLES
    # ---------------------------------------------------------

    def validate_required_tables(self):

        expected_tables = {
            "customer_analytics",
            "product_analytics",
            "category_analytics",
            "business_kpi_summary",
            "funnel_summary",
            "daily_analytics",
            "weekly_analytics",
            "monthly_analytics"
        }

        actual_tables = set(
            self.analytics_tables.keys()
        )

        missing = (
            expected_tables
            - actual_tables
        )

        self._record_check(
            "required_tables_present",
            not missing,
            f"Missing analytics tables: "
            f"{sorted(missing)}"
        )

    # ---------------------------------------------------------
    # ROW COUNTS
    # ---------------------------------------------------------

    def validate_row_counts(self):

        customer_rows = self.analytics_tables[
            "customer_analytics"
        ]

        product_rows = self.analytics_tables[
            "product_analytics"
        ]

        daily_rows = self.analytics_tables[
            "daily_analytics"
        ]

        self._record_check(
            "customer_row_count",
            len(customer_rows)
            == len(self.state.customers),
            "Customer analytics row count mismatch"
        )

        self._record_check(
            "product_row_count",
            len(product_rows)
            == len(self.config["products"]),
            "Product analytics row count mismatch"
        )

        self._record_check(
            "daily_row_count",
            len(daily_rows)
            == self.state.current_day,
            "Daily analytics row count mismatch"
        )

    # ---------------------------------------------------------
    # UNIQUE ANALYTICS KEYS
    # ---------------------------------------------------------

    def validate_unique_keys(self):

        checks = [
            (
                "customer_analytics",
                "customer_id"
            ),
            (
                "product_analytics",
                "product_id"
            ),
            (
                "category_analytics",
                "category"
            )
        ]

        for table_name, key_name in checks:

            rows = self.analytics_tables[
                table_name
            ]

            values = [
                row.get(key_name)
                for row in rows
            ]

            passed = (
                len(values)
                == len(set(values))
                and None not in values
            )

            self._record_check(
                f"{table_name}_unique_{key_name}",
                passed,
                (
                    f"{table_name}: "
                    f"duplicate or missing "
                    f"{key_name}"
                )
            )

    # ---------------------------------------------------------
    # BUSINESS TOTALS
    # ---------------------------------------------------------

    def validate_business_totals(self):

        expected_orders = len(
            self.state.orders
        )

        expected_events = len(
            self.state.events
        )

        expected_revenue = sum(
            order.get(
                "gross_amount",
                0
            )
            for order
            in self.state.orders.values()
        )

        # ---------------------------------------------
        # Daily
        # ---------------------------------------------

        daily = self.analytics_tables[
            "daily_analytics"
        ]

        daily_orders = sum(
            row["orders"]
            for row in daily
        )

        daily_events = sum(
            row["events"]
            for row in daily
        )

        daily_revenue = sum(
            row["revenue"]
            for row in daily
        )

        self._record_check(
            "daily_orders_reconcile",
            daily_orders
            == expected_orders,
            "Daily order totals do not reconcile"
        )

        self._record_check(
            "daily_events_reconcile",
            daily_events
            == expected_events,
            "Daily event totals do not reconcile"
        )

        self._record_check(
            "daily_revenue_reconcile",
            abs(
                daily_revenue
                - expected_revenue
            ) <= 0.01,
            "Daily revenue does not reconcile"
        )

        # ---------------------------------------------
        # Weekly
        # ---------------------------------------------

        weekly = self.analytics_tables[
            "weekly_analytics"
        ]

        self._record_check(
            "weekly_orders_reconcile",
            sum(
                row["orders"]
                for row in weekly
            ) == expected_orders,
            "Weekly order totals do not reconcile"
        )

        self._record_check(
            "weekly_events_reconcile",
            sum(
                row["events"]
                for row in weekly
            ) == expected_events,
            "Weekly event totals do not reconcile"
        )

        self._record_check(
            "weekly_revenue_reconcile",
            abs(
                sum(
                    row["revenue"]
                    for row in weekly
                )
                - expected_revenue
            ) <= 0.01,
            "Weekly revenue does not reconcile"
        )

        # ---------------------------------------------
        # Monthly
        # ---------------------------------------------

        monthly = self.analytics_tables[
            "monthly_analytics"
        ]

        if not monthly:

            self.errors.append(
                "Monthly analytics is empty"
            )

        else:

            month = monthly[0]

            self._record_check(
                "monthly_orders_reconcile",
                month["orders"]
                == expected_orders,
                "Monthly order total does not reconcile"
            )

            self._record_check(
                "monthly_events_reconcile",
                month["events"]
                == expected_events,
                "Monthly event total does not reconcile"
            )

            self._record_check(
                "monthly_revenue_reconcile",
                abs(
                    month["revenue"]
                    - expected_revenue
                ) <= 0.01,
                "Monthly revenue does not reconcile"
            )

    # ---------------------------------------------------------
    # PRODUCT / CATEGORY TOTALS
    # ---------------------------------------------------------

    def validate_product_totals(self):

        expected_orders = len(
            self.state.orders
        )

        expected_revenue = sum(
            order.get(
                "gross_amount",
                0
            )
            for order
            in self.state.orders.values()
        )

        products = self.analytics_tables[
            "product_analytics"
        ]

        categories = self.analytics_tables[
            "category_analytics"
        ]

        self._record_check(
            "product_orders_reconcile",
            sum(
                row["orders"]
                for row in products
            ) == expected_orders,
            "Product order totals do not reconcile"
        )

        self._record_check(
            "product_revenue_reconcile",
            abs(
                sum(
                    row["revenue"]
                    for row in products
                )
                - expected_revenue
            ) <= 0.01,
            "Product revenue does not reconcile"
        )

        self._record_check(
            "category_orders_reconcile",
            sum(
                row["orders"]
                for row in categories
            ) == expected_orders,
            "Category order totals do not reconcile"
        )

        self._record_check(
            "category_revenue_reconcile",
            abs(
                sum(
                    row["revenue"]
                    for row in categories
                )
                - expected_revenue
            ) <= 0.01,
            "Category revenue does not reconcile"
        )

    # ---------------------------------------------------------
    # FUNNEL RECONCILIATION
    # ---------------------------------------------------------

    def validate_funnel(self):

        funnel_rows = self.analytics_tables[
            "funnel_summary"
        ]

        if not funnel_rows:

            self.errors.append(
                "Funnel summary is empty"
            )
            return

        funnel = funnel_rows[0]

        purchases = funnel.get(
            "event_counts_purchases"
        )

        self._record_check(
            "funnel_purchase_reconcile",
            purchases == len(
                self.state.orders
            ),
            (
                "Funnel purchase count does "
                "not match order count"
            )
        )

    # ---------------------------------------------------------
    # EXPORTED CSV FILES
    # ---------------------------------------------------------

    def validate_exports(self):

        analytics_directory = Path(
            self.analytics_export_result[
                "analytics_directory"
            ]
        )

        export_tables = (
            self.analytics_export_result[
                "tables"
            ]
        )

        for table_name, rows in (
            self.analytics_tables.items()
        ):

            summary = export_tables.get(
                table_name
            )

            if summary is None:

                self.errors.append(
                    f"Missing export summary: "
                    f"{table_name}"
                )
                continue

            file_name = summary.get(
                "file"
            )

            if file_name is None:

                self.errors.append(
                    f"Missing CSV file: "
                    f"{table_name}"
                )
                continue

            file_path = (
                analytics_directory
                / file_name
            )

            if not file_path.exists():

                self.errors.append(
                    f"Analytics CSV not found: "
                    f"{file_path}"
                )
                continue

            with file_path.open(
                "r",
                newline="",
                encoding="utf-8"
            ) as file:

                reader = csv.DictReader(
                    file
                )

                csv_rows = list(
                    reader
                )

            self._record_check(
                f"{table_name}_export_row_count",
                len(csv_rows)
                == len(rows),
                (
                    f"{table_name}: "
                    f"exported CSV row count "
                    f"does not match analytics table"
                )
            )

        manifest = Path(
            self.analytics_export_result[
                "manifest"
            ]
        )

        self._record_check(
            "analytics_manifest_exists",
            manifest.exists(),
            "Analytics manifest does not exist"
        )

    # ---------------------------------------------------------
    # COMPLETE VALIDATION
    # ---------------------------------------------------------

    def validate_all(self):

        self.errors = []
        self.checks = {}

        self.validate_required_tables()
        self.validate_row_counts()
        self.validate_unique_keys()
        self.validate_business_totals()
        self.validate_product_totals()
        self.validate_funnel()
        self.validate_exports()

        return {
            "passed":
                len(self.errors) == 0,

            "error_count":
                len(self.errors),

            "errors":
                self.errors,

            "checks":
                self.checks
        }