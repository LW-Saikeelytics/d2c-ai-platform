import statistics

class MultiDayAnalytics:

    def __init__(self, daily_analytics):
        self.daily_analytics = daily_analytics

    # ============================================================
    # PERIOD SUMMARY
    # ============================================================

    def calculate_period_summary(self):

        total_days = len(self.daily_analytics)

        if total_days == 0:
            return {
                "simulation_days": 0,
                "total_orders": 0,
                "total_events": 0,
                "total_revenue": 0.0,
                "average_daily_orders": 0.0,
                "average_daily_events": 0.0,
                "average_daily_revenue": 0.0,
                "active_days": 0,
                "zero_activity_days": 0
            }

        # --------------------------------------------------------
        # TOTALS
        # --------------------------------------------------------

        total_orders = sum(
            day["orders"]
            for day in self.daily_analytics
        )

        total_events = sum(
            day["events"]
            for day in self.daily_analytics
        )

        total_revenue = sum(
            day["revenue"]
            for day in self.daily_analytics
        )

        # --------------------------------------------------------
        # ACTIVITY DAYS
        # --------------------------------------------------------

        active_days = sum(
            1
            for day in self.daily_analytics
            if day["events"] > 0
        )

        zero_activity_days = (
            total_days - active_days
        )

        # --------------------------------------------------------
        # DAILY AVERAGES
        # --------------------------------------------------------

        average_daily_orders = (
            total_orders / total_days
        )

        average_daily_events = (
            total_events / total_days
        )

        average_daily_revenue = (
            total_revenue / total_days
        )

        # --------------------------------------------------------
        # RESULT
        # --------------------------------------------------------

        return {
            "simulation_days": total_days,

            "total_orders": total_orders,
            "total_events": total_events,
            "total_revenue": round(
                total_revenue,
                2
            ),

            "average_daily_orders": round(
                average_daily_orders,
                4
            ),

            "average_daily_events": round(
                average_daily_events,
                4
            ),

            "average_daily_revenue": round(
                average_daily_revenue,
                2
            ),

            "active_days": active_days,
            "zero_activity_days": zero_activity_days
        }

    # ============================================================
    # DAILY TREND METRICS
    # ============================================================

    def calculate_daily_trends(self):

        if not self.daily_analytics:
            return {
                "peak_order_day": None,
                "peak_event_day": None,
                "peak_revenue_day": None,
                "highest_orders": 0,
                "highest_events": 0,
                "highest_revenue": 0.0,
                "order_change_days": 0,
                "event_change_days": 0,
                "revenue_change_days": 0
            }

        # --------------------------------------------------------
        # PEAK DAYS
        # --------------------------------------------------------

        peak_order_record = max(
            self.daily_analytics,
            key=lambda day: day["orders"]
        )

        peak_event_record = max(
            self.daily_analytics,
            key=lambda day: day["events"]
        )

        peak_revenue_record = max(
            self.daily_analytics,
            key=lambda day: day["revenue"]
        )

        # --------------------------------------------------------
        # DAY-TO-DAY CHANGES
        # --------------------------------------------------------

        order_change_days = 0
        event_change_days = 0
        revenue_change_days = 0

        for index in range(
            1,
            len(self.daily_analytics)
        ):

            previous_day = self.daily_analytics[index - 1]
            current_day = self.daily_analytics[index]

            if (
                current_day["orders"]
                != previous_day["orders"]
            ):
                order_change_days += 1

            if (
                current_day["events"]
                != previous_day["events"]
            ):
                event_change_days += 1

            if (
                current_day["revenue"]
                != previous_day["revenue"]
            ):
                revenue_change_days += 1

        # --------------------------------------------------------
        # RESULT
        # --------------------------------------------------------

        return {
            "peak_order_day": (
                peak_order_record["simulation_day"]
            ),
            "peak_event_day": (
                peak_event_record["simulation_day"]
            ),
            "peak_revenue_day": (
                peak_revenue_record["simulation_day"]
            ),

            "highest_orders": (
                peak_order_record["orders"]
            ),
            "highest_events": (
                peak_event_record["events"]
            ),
            "highest_revenue": round(
                peak_revenue_record["revenue"],
                2
            ),

            "order_change_days": order_change_days,
            "event_change_days": event_change_days,
            "revenue_change_days": revenue_change_days
        }

    # ============================================================
    # ACTIVITY / REVENUE STABILITY
    # ============================================================

    def calculate_stability_metrics(self):

        if not self.daily_analytics:
            return {
                "order_std_dev": 0.0,
                "event_std_dev": 0.0,
                "revenue_std_dev": 0.0,
                "order_cv": 0.0,
                "event_cv": 0.0,
                "revenue_cv": 0.0
            }

        daily_orders = [
            day["orders"]
            for day in self.daily_analytics
        ]

        daily_events = [
            day["events"]
            for day in self.daily_analytics
        ]

        daily_revenue = [
            day["revenue"]
            for day in self.daily_analytics
        ]

        # --------------------------------------------------------
        # MEANS
        # --------------------------------------------------------

        mean_orders = statistics.mean(daily_orders)
        mean_events = statistics.mean(daily_events)
        mean_revenue = statistics.mean(daily_revenue)

        # --------------------------------------------------------
        # POPULATION STANDARD DEVIATION
        # --------------------------------------------------------

        order_std_dev = statistics.pstdev(
            daily_orders
        )

        event_std_dev = statistics.pstdev(
            daily_events
        )

        revenue_std_dev = statistics.pstdev(
            daily_revenue
        )

        # --------------------------------------------------------
        # COEFFICIENT OF VARIATION
        # --------------------------------------------------------

        order_cv = (
            order_std_dev / mean_orders
            if mean_orders > 0
            else 0.0
        )

        event_cv = (
            event_std_dev / mean_events
            if mean_events > 0
            else 0.0
        )

        revenue_cv = (
            revenue_std_dev / mean_revenue
            if mean_revenue > 0
            else 0.0
        )

        return {
            "order_std_dev": round(
                order_std_dev,
                4
            ),

            "event_std_dev": round(
                event_std_dev,
                4
            ),

            "revenue_std_dev": round(
                revenue_std_dev,
                2
            ),

            "order_cv": round(
                order_cv,
                4
            ),

            "event_cv": round(
                event_cv,
                4
            ),

            "revenue_cv": round(
                revenue_cv,
                4
            )
        }    