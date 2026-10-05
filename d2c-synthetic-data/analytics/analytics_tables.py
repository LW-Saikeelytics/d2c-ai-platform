class AnalyticsTableBuilder:

    def __init__(
        self,
        state,
        config,
        business_kpis,
        product_result,
        retention_result,
        funnel_result,
        daily_analytics,
        weekly_analytics,
        monthly_analytics
    ):
        self.state = state
        self.config = config

        self.business_kpis = business_kpis
        self.product_result = product_result
        self.retention_result = retention_result
        self.funnel_result = funnel_result

        self.daily_analytics = daily_analytics
        self.weekly_analytics = weekly_analytics
        self.monthly_analytics = monthly_analytics

    # ---------------------------------------------------------
    # CUSTOMER ANALYTICS TABLE
    # ---------------------------------------------------------

    def build_customer_table(self):

        retention_detail = (
            self.retention_result[
                "customer_detail"
            ]
        )

        rows = []

        for customer_id, customer in (
            self.state.customers.items()
        ):

            retention = retention_detail.get(
                customer_id,
                {}
            )

            rows.append(
                {
                    "customer_id":
                        customer_id,

                    "segment":
                        customer.get("segment"),

                    "city_id":
                        customer.get("city_id"),

                    "region":
                        customer.get("region"),

                    "acquisition_channel":
                        customer.get(
                            "acquisition_channel"
                        ),

                    "lifetime_orders":
                        customer.get(
                            "lifetime_orders",
                            0
                        ),

                    "lifetime_spend":
                        customer.get(
                            "lifetime_spend",
                            0
                        ),

                    "purchase_propensity":
                        customer.get(
                            "purchase_propensity"
                        ),

                    "status":
                        customer.get("status"),

                    "first_purchase_day":
                        retention.get(
                            "first_purchase_day"
                        ),

                    "last_purchase_day":
                        retention.get(
                            "last_purchase_day"
                        ),

                    "repeat_customer":
                        retention.get(
                            "repeat_customer",
                            False
                        ),

                    "returned_on_later_day":
                        retention.get(
                            "returned_on_later_day",
                            False
                        )
                }
            )

        return rows

    # ---------------------------------------------------------
    # PRODUCT ANALYTICS TABLE
    # ---------------------------------------------------------

    def build_product_table(self):

        product_performance = (
            self.product_result[
                "product_performance"
            ]
        )

        rows = []

        for product in self.config["products"]:

            product_id = product[
                "product_id"
            ]

            performance = (
                product_performance.get(
                    product_id,
                    {}
                )
            )

            orders = performance.get(
                "orders",
                0
            )

            revenue = performance.get(
                "revenue",
                0
            )

            rows.append(
                {
                    "product_id":
                        product_id,

                    "category":
                        product.get(
                            "category"
                        ),

                    "subcategory":
                        product.get(
                            "subcategory"
                        ),

                    "orders":
                        orders,

                    "units_sold":
                        performance.get(
                            "units_sold",
                            0
                        ),

                    "revenue":
                        revenue,

                    "unique_customers":
                        performance.get(
                            "unique_customers",
                            0
                        ),

                    "average_order_value":
                        round(
                            revenue / orders,
                            2
                        )
                        if orders
                        else 0
                }
            )

        return rows

    # ---------------------------------------------------------
    # CATEGORY ANALYTICS TABLE
    # ---------------------------------------------------------

    def build_category_table(self):

        category_performance = (
            self.product_result[
                "category_performance"
            ]
        )

        categories = sorted(
            {
                product.get("category")
                for product
                in self.config["products"]
                if product.get("category")
            }
        )

        rows = []

        for category in categories:

            performance = (
                category_performance.get(
                    category,
                    {}
                )
            )

            rows.append(
                {
                    "category":
                        category,

                    "orders":
                        performance.get(
                            "orders",
                            0
                        ),

                    "units_sold":
                        performance.get(
                            "units_sold",
                            0
                        ),

                    "revenue":
                        performance.get(
                            "revenue",
                            0
                        ),

                    "unique_customers":
                        performance.get(
                            "unique_customers",
                            0
                        ),

                    "average_order_value":
                        performance.get(
                            "average_order_value",
                            0
                        )
                }
            )

        return rows

    # ---------------------------------------------------------
    # BUSINESS KPI SUMMARY TABLE
    # ---------------------------------------------------------

    def build_kpi_summary_table(self):

        row = {}

        for section, metrics in (
            self.business_kpis.items()
        ):

            for metric_name, value in (
                metrics.items()
            ):

                key = (
                    f"{section}_"
                    f"{metric_name}"
                )

                row[key] = value

        return [row]

    # ---------------------------------------------------------
    # FUNNEL SUMMARY TABLE
    # ---------------------------------------------------------

    def build_funnel_table(self):

        row = {}

        for section, metrics in (
            self.funnel_result.items()
        ):

            for metric_name, value in (
                metrics.items()
            ):

                row[
                    f"{section}_{metric_name}"
                ] = value

        return [row]

    # ---------------------------------------------------------
    # COMPLETE ANALYTICS DATASET
    # ---------------------------------------------------------

    def build_all(self):

        return {
            "customer_analytics":
                self.build_customer_table(),

            "product_analytics":
                self.build_product_table(),

            "category_analytics":
                self.build_category_table(),

            "business_kpi_summary":
                self.build_kpi_summary_table(),

            "funnel_summary":
                self.build_funnel_table(),

            "daily_analytics":
                list(
                    self.daily_analytics
                ),

            "weekly_analytics":
                list(
                    self.weekly_analytics
                ),

            "monthly_analytics": [
                dict(
                    self.monthly_analytics
                )
            ]
        }