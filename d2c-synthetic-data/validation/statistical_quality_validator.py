class StatisticalQualityValidator:

    def __init__(self, simulation_state):
        self.state = simulation_state

        self.errors = []
        self.warnings = []
        self.checks = {}

    # ============================================================
    # CORE DATASET STATISTICS
    # ============================================================

    def calculate_core_statistics(self):

        customer_count = len(self.state.customers)
        order_count = len(self.state.orders)
        event_count = len(self.state.events)

        # --------------------------------------------------------
        # REVENUE
        # --------------------------------------------------------

        total_revenue = sum(
            order.get("gross_amount", 0)
            for order in self.state.orders.values()
        )

        average_order_value = (
            total_revenue / order_count
            if order_count > 0
            else 0.0
        )

        # --------------------------------------------------------
        # CONVERSION
        # --------------------------------------------------------

        customers_with_orders = {
            order.get("customer_id")
            for order in self.state.orders.values()
            if order.get("customer_id") is not None
        }

        customer_conversion_rate = (
            len(customers_with_orders) / customer_count
            if customer_count > 0
            else 0.0
        )

        # --------------------------------------------------------
        # EVENTS
        # --------------------------------------------------------

        events_per_customer = (
            event_count / customer_count
            if customer_count > 0
            else 0.0
        )

        orders_per_customer = (
            order_count / customer_count
            if customer_count > 0
            else 0.0
        )

        # --------------------------------------------------------
        # RESULTS
        # --------------------------------------------------------

        self.checks["core_statistics"] = {
            "customer_count": customer_count,
            "order_count": order_count,
            "event_count": event_count,
            "total_revenue": round(total_revenue, 2),
            "average_order_value": round(
                average_order_value,
                2
            ),
            "customers_with_orders": len(
                customers_with_orders
            ),
            "customer_conversion_rate": round(
                customer_conversion_rate,
                4
            ),
            "events_per_customer": round(
                events_per_customer,
                4
            ),
            "orders_per_customer": round(
                orders_per_customer,
                4
            )
        }

    # ============================================================
    # EVENT DISTRIBUTION
    # ============================================================

    def calculate_event_distribution(self):

        event_type_counts = {}

        for event in self.state.events.values():

            event_type = event.get("event_type")

            if event_type is None:
                continue

            event_type_counts[event_type] = (
                event_type_counts.get(event_type, 0) + 1
            )

        total_events = len(self.state.events)
        event_type_percentages = {}

        for event_type, count in event_type_counts.items():

            percentage = (
                count / total_events
                if total_events > 0
                else 0.0
            )

            event_type_percentages[event_type] = round(
                percentage,
                4
            )

        self.checks["event_distribution"] = {
            "counts": event_type_counts,
            "percentages": event_type_percentages
        }

    # ============================================================
    # ORDER / REVENUE DISTRIBUTION
    # ============================================================

    def calculate_order_revenue_distribution(self):

        orders_per_customer = {}
        revenue_per_customer = {}

        order_values = []

        # --------------------------------------------------------
        # BUILD CUSTOMER DISTRIBUTIONS
        # --------------------------------------------------------

        for order in self.state.orders.values():

            customer_id = order.get("customer_id")
            gross_amount = order.get("gross_amount")

            if customer_id is None:
                continue

            orders_per_customer[customer_id] = (
                orders_per_customer.get(customer_id, 0) + 1
            )

            if gross_amount is not None:

                revenue_per_customer[customer_id] = (
                    revenue_per_customer.get(customer_id, 0.0)
                    + gross_amount
                )

                order_values.append(gross_amount)

        # --------------------------------------------------------
        # ORDER VALUE STATISTICS
        # --------------------------------------------------------

        if order_values:

            minimum_order_value = min(order_values)
            maximum_order_value = max(order_values)

            average_order_value = (
                sum(order_values) / len(order_values)
            )

        else:

            minimum_order_value = 0.0
            maximum_order_value = 0.0
            average_order_value = 0.0

        # --------------------------------------------------------
        # CUSTOMER ORDER STATISTICS
        # --------------------------------------------------------

        if orders_per_customer:

            maximum_orders_by_customer = max(
                orders_per_customer.values()
            )

        else:

            maximum_orders_by_customer = 0

        # --------------------------------------------------------
        # RESULTS
        # --------------------------------------------------------

        self.checks["order_revenue_distribution"] = {
            "orders_per_customer": orders_per_customer,
            "revenue_per_customer": {
                customer_id: round(revenue, 2)
                for customer_id, revenue
                in revenue_per_customer.items()
            },
            "minimum_order_value": round(
                minimum_order_value,
                2
            ),
            "maximum_order_value": round(
                maximum_order_value,
                2
            ),
            "average_order_value": round(
                average_order_value,
                2
            ),
            "maximum_orders_by_customer": (
                maximum_orders_by_customer
            )
        }

    # ============================================================
    # CATEGORY DISTRIBUTION
    # ============================================================

    def calculate_category_distribution(self):

        order_counts_by_category = {}
        revenue_by_category = {}
        event_counts_by_category = {}

        # --------------------------------------------------------
        # ORDER CATEGORY DISTRIBUTION
        # --------------------------------------------------------

        for order in self.state.orders.values():

            category = order.get("category")
            gross_amount = order.get("gross_amount")

            if category is None:
                continue

            order_counts_by_category[category] = (
                order_counts_by_category.get(category, 0) + 1
            )

            if gross_amount is not None:
                revenue_by_category[category] = (
                    revenue_by_category.get(category, 0.0)
                    + gross_amount
                )

        # --------------------------------------------------------
        # EVENT CATEGORY DISTRIBUTION
        # --------------------------------------------------------

        for event in self.state.events.values():

            category = event.get("category")

            if category is None:
                continue

            event_counts_by_category[category] = (
                event_counts_by_category.get(category, 0) + 1
            )

        # --------------------------------------------------------
        # RESULTS
        # --------------------------------------------------------

        self.checks["category_distribution"] = {
            "order_counts": order_counts_by_category,

            "revenue": {
                category: round(revenue, 2)
                for category, revenue
                in revenue_by_category.items()
            },

            "event_counts": event_counts_by_category
        }

    # ============================================================
    # DAILY DISTRIBUTION
    # ============================================================

    def calculate_daily_distribution(self):

        orders_by_day = {}
        events_by_day = {}
        revenue_by_day = {}

        # --------------------------------------------------------
        # ORDERS BY DAY
        # --------------------------------------------------------

        for order in self.state.orders.values():

            simulation_day = order.get("simulation_day")
            gross_amount = order.get("gross_amount")

            if simulation_day is None:
                continue

            orders_by_day[simulation_day] = (
                orders_by_day.get(simulation_day, 0) + 1
            )

            if gross_amount is not None:
                revenue_by_day[simulation_day] = (
                    revenue_by_day.get(simulation_day, 0.0)
                    + gross_amount
                )

        # --------------------------------------------------------
        # EVENTS BY DAY
        # --------------------------------------------------------

        for event in self.state.events.values():

            simulation_day = event.get("simulation_day")

            if simulation_day is None:
                continue

            events_by_day[simulation_day] = (
                events_by_day.get(simulation_day, 0) + 1
            )

        # --------------------------------------------------------
        # INCLUDE ZERO-ACTIVITY DAYS
        # --------------------------------------------------------

        daily_distribution = {}

        for day in range(1, self.state.current_day + 1):

            daily_distribution[day] = {
                "orders": orders_by_day.get(day, 0),
                "events": events_by_day.get(day, 0),
                "revenue": round(
                    revenue_by_day.get(day, 0.0),
                    2
                )
            }

        # --------------------------------------------------------
        # RESULTS
        # --------------------------------------------------------

        self.checks["daily_distribution"] = daily_distribution

    # ============================================================
    # STATISTICAL ANOMALY WARNINGS
    # ============================================================

    def detect_statistical_anomalies(self):

        anomaly_count = 0

        customer_count = len(self.state.customers)
        order_count = len(self.state.orders)
        event_count = len(self.state.events)

        # --------------------------------------------------------
        # SMALL SAMPLE SIZE
        # --------------------------------------------------------

        if order_count < 30:

            anomaly_count += 1

            self.warnings.append(
                f"Statistical sample is small: only "
                f"{order_count} orders are available. "
                f"Distribution metrics should be interpreted cautiously."
            )

        # --------------------------------------------------------
        # ZERO-ACTIVITY DAYS
        # --------------------------------------------------------

        zero_activity_days = 0
        total_days = self.state.current_day

        for day in range(1, total_days + 1):

            day_events = sum(
                1
                for event in self.state.events.values()
                if event.get("simulation_day") == day
            )

            if day_events == 0:
                zero_activity_days += 1

        zero_activity_ratio = (
            zero_activity_days / total_days
            if total_days > 0
            else 0.0
        )

        if zero_activity_ratio > 0.5:

            anomaly_count += 1

            self.warnings.append(
                f"{zero_activity_days} of {total_days} simulation days "
                f"contain no events."
            )

        # --------------------------------------------------------
        # REVENUE CONCENTRATION
        # --------------------------------------------------------

        total_revenue = sum(
            order.get("gross_amount", 0)
            for order in self.state.orders.values()
        )

        order_values = [
            order.get("gross_amount", 0)
            for order in self.state.orders.values()
        ]

        largest_order_share = 0.0

        if total_revenue > 0 and order_values:

            largest_order = max(order_values)

            largest_order_share = (
                largest_order / total_revenue
            )

            # Only treat this as meaningful when enough orders exist.
            if (
                order_count >= 20
                and largest_order_share > 0.5
            ):

                anomaly_count += 1

                self.warnings.append(
                    f"Largest order contributes "
                    f"{largest_order_share:.2%} of total revenue."
                )

        # --------------------------------------------------------
        # EVENT TYPE CONCENTRATION
        # --------------------------------------------------------

        event_type_counts = {}

        for event in self.state.events.values():

            event_type = event.get("event_type")

            if event_type is None:
                continue

            event_type_counts[event_type] = (
                event_type_counts.get(event_type, 0) + 1
            )

        dominant_event_share = 0.0
        dominant_event_type = None

        if event_count > 0 and event_type_counts:

            dominant_event_type = max(
                event_type_counts,
                key=event_type_counts.get
            )

            dominant_event_share = (
                event_type_counts[dominant_event_type]
                / event_count
            )

            if (
                event_count >= 50
                and dominant_event_share > 0.70
            ):

                anomaly_count += 1

                self.warnings.append(
                    f"Event type '{dominant_event_type}' accounts for "
                    f"{dominant_event_share:.2%} of all events."
                )

        # --------------------------------------------------------
        # RESULTS
        # --------------------------------------------------------

        self.checks["statistical_anomalies"] = {
            "anomaly_count": anomaly_count,
            "small_sample": order_count < 30,
            "zero_activity_days": zero_activity_days,
            "zero_activity_ratio": round(
                zero_activity_ratio,
                4
            ),
            "largest_order_revenue_share": round(
                largest_order_share,
                4
            ),
            "dominant_event_type": dominant_event_type,
            "dominant_event_share": round(
                dominant_event_share,
                4
            )
        }

    # ============================================================
    # MAIN VALIDATION
    # ============================================================

    def validate_all(self):

        self.errors = []
        self.warnings = []
        self.checks = {}

        self.calculate_core_statistics()
        self.calculate_event_distribution()
        self.calculate_order_revenue_distribution()
        self.calculate_category_distribution()
        self.calculate_daily_distribution()
        self.detect_statistical_anomalies()

        return {
            "passed": len(self.errors) == 0,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
            "checks": self.checks
        }