class BusinessKPIAnalytics:

    def __init__(self, state):
        self.state = state

    # ---------------------------------------------------------
    # CUSTOMER METRICS
    # ---------------------------------------------------------

    def calculate_customer_metrics(self):

        total_customers = len(
            self.state.customers
        )

        customer_ids_with_orders = {
            order["customer_id"]
            for order in self.state.orders.values()
        }

        customers_with_orders = len(
            customer_ids_with_orders
        )

        customers_without_orders = (
            total_customers
            - customers_with_orders
        )

        customer_purchase_rate = (
            customers_with_orders / total_customers
            if total_customers
            else 0
        )

        average_orders_per_customer = (
            len(self.state.orders)
            / total_customers
            if total_customers
            else 0
        )

        return {
            "total_customers": total_customers,

            "customers_with_orders":
                customers_with_orders,

            "customers_without_orders":
                customers_without_orders,

            "customer_purchase_rate": round(
                customer_purchase_rate,
                4
            ),

            "average_orders_per_customer": round(
                average_orders_per_customer,
                4
            )
        }

    # ---------------------------------------------------------
    # ORDER METRICS
    # ---------------------------------------------------------

    def calculate_order_metrics(self):

        orders = list(
            self.state.orders.values()
        )

        total_orders = len(orders)

        total_units = sum(
            order.get("quantity", 0)
            for order in orders
        )

        order_values = [
            order.get("gross_amount", 0)
            for order in orders
        ]

        average_order_value = (
            sum(order_values) / total_orders
            if total_orders
            else 0
        )

        average_units_per_order = (
            total_units / total_orders
            if total_orders
            else 0
        )

        return {
            "total_orders": total_orders,

            "total_units_sold": total_units,

            "average_order_value": round(
                average_order_value,
                2
            ),

            "average_units_per_order": round(
                average_units_per_order,
                4
            ),

            "minimum_order_value": round(
                min(order_values),
                2
            ) if order_values else 0,

            "maximum_order_value": round(
                max(order_values),
                2
            ) if order_values else 0
        }

    # ---------------------------------------------------------
    # CONVERSION METRICS
    # ---------------------------------------------------------

    def calculate_conversion_metrics(self):

        conversion_records = (
            self.state.conversion_history
        )

        customers_evaluated = len(
            conversion_records
        )

        successful_conversions = sum(
            1
            for record in conversion_records
            if record.get(
                "result",
                {}
            ).get("converted") is True
        )

        conversion_rate = (
            successful_conversions
            / customers_evaluated
            if customers_evaluated
            else 0
        )

        return {
            "conversion_evaluations":
                customers_evaluated,

            "successful_conversions":
                successful_conversions,

            "conversion_rate": round(
                conversion_rate,
                4
            )
        }

    # ---------------------------------------------------------
    # REVENUE METRICS
    # ---------------------------------------------------------

    def calculate_revenue_metrics(self):

        total_revenue = sum(
            order.get("gross_amount", 0)
            for order in self.state.orders.values()
        )

        total_customers = len(
            self.state.customers
        )

        purchasing_customers = {
            order["customer_id"]
            for order in self.state.orders.values()
        }

        simulation_days = (
            self.state.current_day
        )

        average_daily_revenue = (
            total_revenue / simulation_days
            if simulation_days
            else 0
        )

        revenue_per_customer = (
            total_revenue / total_customers
            if total_customers
            else 0
        )

        revenue_per_purchasing_customer = (
            total_revenue
            / len(purchasing_customers)
            if purchasing_customers
            else 0
        )

        return {
            "total_revenue": round(
                total_revenue,
                2
            ),

            "average_daily_revenue": round(
                average_daily_revenue,
                2
            ),

            "revenue_per_customer": round(
                revenue_per_customer,
                2
            ),

            "revenue_per_purchasing_customer": round(
                revenue_per_purchasing_customer,
                2
            )
        }

    # ---------------------------------------------------------
    # COMPLETE KPI REPORT
    # ---------------------------------------------------------

    def calculate_all(self):

        return {
            "customer_metrics":
                self.calculate_customer_metrics(),

            "order_metrics":
                self.calculate_order_metrics(),

            "conversion_metrics":
                self.calculate_conversion_metrics(),

            "revenue_metrics":
                self.calculate_revenue_metrics()
        }