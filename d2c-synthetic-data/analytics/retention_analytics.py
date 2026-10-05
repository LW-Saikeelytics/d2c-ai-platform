from collections import defaultdict
from statistics import mean


class RetentionAnalytics:

    def __init__(self, state):
        self.state = state

    # ---------------------------------------------------------
    # BUILD CUSTOMER PURCHASE HISTORY
    # ---------------------------------------------------------

    def build_customer_purchase_history(self):

        history = defaultdict(list)

        for order in self.state.orders.values():

            customer_id = order["customer_id"]

            history[customer_id].append(
                {
                    "order_id": order["order_id"],
                    "simulation_day": order["simulation_day"],
                    "gross_amount": order.get(
                        "gross_amount",
                        0
                    )
                }
            )

        for customer_id in history:

            history[customer_id].sort(
                key=lambda order:
                    order["simulation_day"]
            )

        return dict(history)

    # ---------------------------------------------------------
    # REPEAT PURCHASE METRICS
    # ---------------------------------------------------------

    def calculate_repeat_purchase_metrics(self):

        history = (
            self.build_customer_purchase_history()
        )

        purchasing_customers = len(history)

        total_orders = len(
            self.state.orders
        )

        one_time_customers = 0
        repeat_customers = 0
        returning_customers = 0

        purchase_gaps = []

        for orders in history.values():

            order_count = len(orders)

            if order_count == 1:
                one_time_customers += 1

            if order_count > 1:
                repeat_customers += 1

            purchase_days = sorted(
                {
                    order["simulation_day"]
                    for order in orders
                }
            )

            # Customer purchased on multiple
            # different simulation days.
            if len(purchase_days) > 1:

                returning_customers += 1

                for index in range(
                    1,
                    len(purchase_days)
                ):

                    gap = (
                        purchase_days[index]
                        - purchase_days[index - 1]
                    )

                    purchase_gaps.append(
                        gap
                    )

        # Every purchasing customer's first order
        # is considered their first purchase.
        first_orders = purchasing_customers

        repeat_orders = (
            total_orders
            - first_orders
        )

        repeat_customer_rate = (
            repeat_customers
            / purchasing_customers
            if purchasing_customers
            else 0
        )

        returning_customer_rate = (
            returning_customers
            / purchasing_customers
            if purchasing_customers
            else 0
        )

        repeat_order_share = (
            repeat_orders
            / total_orders
            if total_orders
            else 0
        )

        average_orders_per_purchaser = (
            total_orders
            / purchasing_customers
            if purchasing_customers
            else 0
        )

        average_days_between_purchases = (
            mean(purchase_gaps)
            if purchase_gaps
            else 0
        )

        return {
            "purchasing_customers":
                purchasing_customers,

            "one_time_customers":
                one_time_customers,

            "repeat_customers":
                repeat_customers,

            "returning_customers":
                returning_customers,

            "repeat_customer_rate": round(
                repeat_customer_rate,
                4
            ),

            "returning_customer_rate": round(
                returning_customer_rate,
                4
            ),

            "first_orders":
                first_orders,

            "repeat_orders":
                repeat_orders,

            "repeat_order_share": round(
                repeat_order_share,
                4
            ),

            "average_orders_per_purchaser": round(
                average_orders_per_purchaser,
                4
            ),

            "average_days_between_purchases": round(
                average_days_between_purchases,
                2
            )
        }

    # ---------------------------------------------------------
    # CUSTOMER-LEVEL RETENTION DETAIL
    # ---------------------------------------------------------

    def calculate_customer_retention_detail(self):

        history = (
            self.build_customer_purchase_history()
        )

        result = {}

        for customer_id, orders in history.items():

            purchase_days = sorted(
                {
                    order["simulation_day"]
                    for order in orders
                }
            )

            result[customer_id] = {
                "total_orders": len(orders),

                "first_purchase_day":
                    purchase_days[0],

                "last_purchase_day":
                    purchase_days[-1],

                "purchase_days":
                    purchase_days,

                "repeat_customer":
                    len(orders) > 1,

                "returned_on_later_day":
                    len(purchase_days) > 1
            }

        return result

    # ---------------------------------------------------------
    # COMPLETE RESULT
    # ---------------------------------------------------------

    def calculate_all(self):

        return {
            "summary":
                self.calculate_repeat_purchase_metrics(),

            "customer_detail":
                self.calculate_customer_retention_detail()
        }