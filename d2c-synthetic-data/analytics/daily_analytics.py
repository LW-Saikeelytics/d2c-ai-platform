class DailyAnalytics:

    def __init__(self, simulation_state):
        self.state = simulation_state

    # ============================================================
    # BUILD DAILY ANALYTICS
    # ============================================================

    def calculate(self):

        analytics = []

        total_customers = len(self.state.customers)

        for day in range(1, self.state.current_day + 1):

            # ----------------------------------------------------
            # DAILY EVENTS
            # ----------------------------------------------------

            daily_events = [
                event
                for event in self.state.events.values()
                if event.get("simulation_day") == day
            ]

            # ----------------------------------------------------
            # DAILY ORDERS
            # ----------------------------------------------------

            daily_orders = [
                order
                for order in self.state.orders.values()
                if order.get("simulation_day") == day
            ]

            # ----------------------------------------------------
            # ACTIVE CUSTOMERS
            # ----------------------------------------------------

            active_customers = {
                event.get("customer_id")
                for event in daily_events
                if event.get("customer_id") is not None
            }

            # ----------------------------------------------------
            # PURCHASING CUSTOMERS
            # ----------------------------------------------------

            purchasing_customers = {
                order.get("customer_id")
                for order in daily_orders
                if order.get("customer_id") is not None
            }

            # ----------------------------------------------------
            # REVENUE
            # ----------------------------------------------------

            revenue = sum(
                order.get("gross_amount", 0)
                for order in daily_orders
            )

            # ----------------------------------------------------
            # METRICS
            # ----------------------------------------------------

            order_count = len(daily_orders)
            event_count = len(daily_events)
            active_customer_count = len(active_customers)

            average_order_value = (
                revenue / order_count
                if order_count > 0
                else 0.0
            )

            conversion_rate = (
                len(purchasing_customers)
                / active_customer_count
                if active_customer_count > 0
                else 0.0
            )

            orders_per_customer = (
                order_count / total_customers
                if total_customers > 0
                else 0.0
            )

            events_per_customer = (
                event_count / total_customers
                if total_customers > 0
                else 0.0
            )

            # ----------------------------------------------------
            # DAILY RESULT
            # ----------------------------------------------------

            analytics.append({
                "simulation_day": day,
                "customers": total_customers,
                "active_customers": active_customer_count,
                "purchasing_customers": len(
                    purchasing_customers
                ),
                "events": event_count,
                "orders": order_count,
                "conversion_rate": round(
                    conversion_rate,
                    4
                ),
                "revenue": round(
                    revenue,
                    2
                ),
                "average_order_value": round(
                    average_order_value,
                    2
                ),
                "orders_per_customer": round(
                    orders_per_customer,
                    4
                ),
                "events_per_customer": round(
                    events_per_customer,
                    4
                )
            })

        return analytics

    # ============================================================
    # VALIDATE DAILY ANALYTICS
    # ============================================================

    def validate(self, analytics):

        errors = []

        # --------------------------------------------------------
        # TOTALS FROM DAILY ANALYTICS
        # --------------------------------------------------------

        analytics_orders = sum(
            day["orders"]
            for day in analytics
        )

        analytics_events = sum(
            day["events"]
            for day in analytics
        )

        analytics_revenue = sum(
            day["revenue"]
            for day in analytics
        )

        # --------------------------------------------------------
        # TOTALS FROM PERSISTENT STATE
        # --------------------------------------------------------

        state_orders = len(self.state.orders)

        state_events = len(self.state.events)

        state_revenue = sum(
            order.get("gross_amount", 0)
            for order in self.state.orders.values()
        )

        # --------------------------------------------------------
        # COMPARE
        # --------------------------------------------------------

        if analytics_orders != state_orders:
            errors.append(
                f"Daily analytics order total '{analytics_orders}' "
                f"does not match state order total '{state_orders}'."
            )

        if analytics_events != state_events:
            errors.append(
                f"Daily analytics event total '{analytics_events}' "
                f"does not match state event total '{state_events}'."
            )

        if abs(analytics_revenue - state_revenue) > 0.01:
            errors.append(
                f"Daily analytics revenue '{analytics_revenue}' "
                f"does not match state revenue '{state_revenue}'."
            )

        # --------------------------------------------------------
        # RESULT
        # --------------------------------------------------------

        return {
            "passed": len(errors) == 0,
            "error_count": len(errors),
            "errors": errors,
            "totals": {
                "orders": analytics_orders,
                "events": analytics_events,
                "revenue": round(analytics_revenue, 2)
            }
        }