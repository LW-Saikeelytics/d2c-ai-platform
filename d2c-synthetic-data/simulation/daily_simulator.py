class DailySimulator:

    def __init__(
        self,
        config,
        state,
        customer_engine,
        bulk_order_engine
    ):
        self.config = config
        self.state = state
        self.customer_engine = customer_engine
        self.bulk_order_engine = bulk_order_engine

    def run_day(self, simulation_day, order_count):

        # Update current simulation day
        self.state.current_day = simulation_day

        # Generate today's orders
        result = self.bulk_order_engine.generate_orders(
            simulation_day=simulation_day,
            order_count=order_count
        )

        # Store today's orders in simulation state
        for order in result["valid_orders"]:
            self.state.orders[order["order_id"]] = order
            self.state.counters["order"] += 1

        return {
            "simulation_day": simulation_day,
            "requested_orders": result["requested"],
            "generated_orders": result["generated"],
            "valid_orders": result["valid"],
            "invalid_orders": result["invalid"]
        }

    def run_days(self, start_day, end_day, orders_per_day):

        daily_results = []

        for day in range(start_day, end_day + 1):

            result = self.run_day(
                simulation_day=day,
                order_count=orders_per_day
            )

            daily_results.append(result)

        return daily_results