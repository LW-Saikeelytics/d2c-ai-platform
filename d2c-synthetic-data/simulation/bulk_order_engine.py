from simulation.order_engine import OrderEngine

class BulkOrderEngine:

    def __init__(self, order_engine, order_validator, customer_engine):
        self.order_engine = order_engine
        self.order_validator = order_validator
        self.customer_engine = customer_engine

    def generate_orders(self, simulation_day, order_count):

        orders = []
        valid_orders = []
        invalid_orders = []

        customers = self.customer_engine.get_customers()

        if not customers:
            raise ValueError("No customers available for order generation.")

        for i in range(order_count):

            customer = self._select_customer(customers)

            order = self.order_engine.generate_order(
                customer,
                simulation_day=simulation_day
            )

            validation = self.order_validator.validate(
                order,
                customer
            )

            orders.append(order)

            if validation["valid"]:
                valid_orders.append(order)

                # Update customer state only after
                # a valid order has been generated.
                self.customer_engine.record_purchase(
                    customer,
                    order
                )

            else:
                invalid_orders.append({
                    "order": order,
                    "errors": validation["errors"]
                })

        return {
            "orders": orders,
            "valid_orders": valid_orders,
            "invalid_orders": invalid_orders,
            "requested": order_count,
            "generated": len(orders),
            "valid": len(valid_orders),
            "invalid": len(invalid_orders)
        }

    def _select_customer(self, customers):

        return self.customer_engine.select_customer_for_order(
            customers
        )