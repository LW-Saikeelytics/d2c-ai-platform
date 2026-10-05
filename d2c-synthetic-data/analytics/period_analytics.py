from collections import defaultdict


class PeriodAnalytics:

    def __init__(self, daily_analytics):
        self.daily_analytics = daily_analytics

    # ---------------------------------------------------------
    # WEEKLY AGGREGATION
    # ---------------------------------------------------------

    def calculate_weekly(self):

        weeks = defaultdict(
            lambda: {
                "days": 0,
                "events": 0,
                "orders": 0,
                "revenue": 0.0,
                "active_customers_total": 0,
                "purchasing_customers_total": 0
            }
        )

        for row in self.daily_analytics:

            day = row["simulation_day"]

            week_number = (
                (day - 1) // 7
            ) + 1

            week = weeks[week_number]

            week["days"] += 1
            week["events"] += row["events"]
            week["orders"] += row["orders"]
            week["revenue"] += row["revenue"]

            week[
                "active_customers_total"
            ] += row["active_customers"]

            week[
                "purchasing_customers_total"
            ] += row["purchasing_customers"]

        result = []

        for week_number in sorted(weeks):

            values = weeks[week_number]

            days = values["days"]
            orders = values["orders"]

            result.append(
                {
                    "week": week_number,

                    "days": days,

                    "events":
                        values["events"],

                    "orders":
                        orders,

                    "revenue": round(
                        values["revenue"],
                        2
                    ),

                    "average_daily_orders": round(
                        orders / days,
                        4
                    ) if days else 0,

                    "average_daily_revenue": round(
                        values["revenue"] / days,
                        2
                    ) if days else 0,

                    "average_order_value": round(
                        values["revenue"] / orders,
                        2
                    ) if orders else 0
                }
            )

        return result

    # ---------------------------------------------------------
    # MONTHLY AGGREGATION
    # ---------------------------------------------------------

    def calculate_monthly(self):

        # Current simulation uses a 30-day analytical month.
        # Later, when simulation dates become central,
        # this can be changed to calendar-month grouping.

        total_days = len(
            self.daily_analytics
        )

        total_events = sum(
            row["events"]
            for row in self.daily_analytics
        )

        total_orders = sum(
            row["orders"]
            for row in self.daily_analytics
        )

        total_revenue = sum(
            row["revenue"]
            for row in self.daily_analytics
        )

        return {
            "simulation_month": 1,

            "days": total_days,

            "events": total_events,

            "orders": total_orders,

            "revenue": round(
                total_revenue,
                2
            ),

            "average_daily_orders": round(
                total_orders / total_days,
                4
            ) if total_days else 0,

            "average_daily_revenue": round(
                total_revenue / total_days,
                2
            ) if total_days else 0,

            "average_order_value": round(
                total_revenue / total_orders,
                2
            ) if total_orders else 0
        }

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------

    def validate(
        self,
        weekly,
        monthly
    ):

        weekly_orders = sum(
            row["orders"]
            for row in weekly
        )

        weekly_events = sum(
            row["events"]
            for row in weekly
        )

        weekly_revenue = sum(
            row["revenue"]
            for row in weekly
        )

        daily_orders = sum(
            row["orders"]
            for row in self.daily_analytics
        )

        daily_events = sum(
            row["events"]
            for row in self.daily_analytics
        )

        daily_revenue = sum(
            row["revenue"]
            for row in self.daily_analytics
        )

        return {
            "weekly_orders_match":
                weekly_orders == daily_orders,

            "weekly_events_match":
                weekly_events == daily_events,

            "weekly_revenue_match":
                abs(
                    weekly_revenue
                    - daily_revenue
                ) <= 0.01,

            "monthly_orders_match":
                monthly["orders"]
                == daily_orders,

            "monthly_events_match":
                monthly["events"]
                == daily_events,

            "monthly_revenue_match":
                abs(
                    monthly["revenue"]
                    - daily_revenue
                ) <= 0.01
        }