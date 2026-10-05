from collections import defaultdict


class ProductAnalytics:

    def __init__(self, state, config):
        self.state = state
        self.config = config

    # ---------------------------------------------------------
    # PRODUCT PERFORMANCE
    # ---------------------------------------------------------

    def calculate_product_performance(self):

        metrics = defaultdict(
            lambda: {
                "orders": 0,
                "units_sold": 0,
                "revenue": 0.0,
                "customers": set()
            }
        )

        for order in self.state.orders.values():

            product_id = order["product_id"]

            product = metrics[product_id]

            product["orders"] += 1
            product["units_sold"] += order.get(
                "quantity",
                0
            )
            product["revenue"] += order.get(
                "gross_amount",
                0
            )
            product["customers"].add(
                order["customer_id"]
            )

        result = {}

        for product_id, values in metrics.items():

            orders = values["orders"]

            result[product_id] = {
                "orders": orders,

                "units_sold":
                    values["units_sold"],

                "revenue": round(
                    values["revenue"],
                    2
                ),

                "unique_customers": len(
                    values["customers"]
                ),

                "average_order_value": round(
                    values["revenue"] / orders,
                    2
                ) if orders else 0
            }

        return result

    # ---------------------------------------------------------
    # CATEGORY PERFORMANCE
    # ---------------------------------------------------------

    def calculate_category_performance(self):

        metrics = defaultdict(
            lambda: {
                "orders": 0,
                "units_sold": 0,
                "revenue": 0.0,
                "customers": set()
            }
        )

        for order in self.state.orders.values():

            category = order["category"]

            values = metrics[category]

            values["orders"] += 1
            values["units_sold"] += order.get(
                "quantity",
                0
            )
            values["revenue"] += order.get(
                "gross_amount",
                0
            )
            values["customers"].add(
                order["customer_id"]
            )

        result = {}

        for category, values in metrics.items():

            orders = values["orders"]

            result[category] = {
                "orders": orders,

                "units_sold":
                    values["units_sold"],

                "revenue": round(
                    values["revenue"],
                    2
                ),

                "unique_customers": len(
                    values["customers"]
                ),

                "average_order_value": round(
                    values["revenue"] / orders,
                    2
                ) if orders else 0
            }

        return result

    # ---------------------------------------------------------
    # PRODUCT SUMMARY
    # ---------------------------------------------------------

    def calculate_summary(self):

        products = (
            self.calculate_product_performance()
        )

        categories = (
            self.calculate_category_performance()
        )

        if not products:
            return {
                "products_with_orders": 0,
                "top_product_by_revenue": None,
                "top_product_by_orders": None,
                "top_category_by_revenue": None,
                "top_category_by_orders": None
            }

        top_product_by_revenue = max(
            products,
            key=lambda product_id:
                products[product_id]["revenue"]
        )

        top_product_by_orders = max(
            products,
            key=lambda product_id:
                products[product_id]["orders"]
        )

        top_category_by_revenue = max(
            categories,
            key=lambda category:
                categories[category]["revenue"]
        )

        top_category_by_orders = max(
            categories,
            key=lambda category:
                categories[category]["orders"]
        )

        return {
            "products_with_orders": len(
                products
            ),

            "top_product_by_revenue":
                top_product_by_revenue,

            "top_product_revenue":
                products[
                    top_product_by_revenue
                ]["revenue"],

            "top_product_by_orders":
                top_product_by_orders,

            "top_product_orders":
                products[
                    top_product_by_orders
                ]["orders"],

            "top_category_by_revenue":
                top_category_by_revenue,

            "top_category_revenue":
                categories[
                    top_category_by_revenue
                ]["revenue"],

            "top_category_by_orders":
                top_category_by_orders,

            "top_category_orders":
                categories[
                    top_category_by_orders
                ]["orders"]
        }

    # ---------------------------------------------------------
    # COMPLETE RESULT
    # ---------------------------------------------------------

    def calculate_all(self):

        return {
            "summary":
                self.calculate_summary(),

            "product_performance":
                self.calculate_product_performance(),

            "category_performance":
                self.calculate_category_performance()
        }