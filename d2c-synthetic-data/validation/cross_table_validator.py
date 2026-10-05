class CrossTableValidator:
    """
    Validates relationships and consistency
    across multiple simulation datasets.
    """

    def __init__(self):
        self.errors = []

    def add_error(self, message):
        self.errors.append(message)

    def has_errors(self):
        return len(self.errors) > 0

    def summary(self):
        return {
            "passed": not self.has_errors(),
            "error_count": len(self.errors),
            "errors": self.errors,
        }

    def validate_order_customers(self, customers, orders):
        """
        Ensures every order references a valid customer.
        """

        customer_ids = set(customers.keys())

        for order_id, order in orders.items():

            customer_id = order.get("customer_id")

            if customer_id not in customer_ids:
                self.add_error(
                    f"Order {order_id} references "
                    f"unknown customer {customer_id}"
                )    

    def validate_event_customers(self, customers, events):
        """
        Ensures every event references a valid customer.
        """

        customer_ids = set(customers.keys())

        for event_id, event in events.items():

            customer_id = event.get("customer_id")

            if customer_id not in customer_ids:
                self.add_error(
                    f"Event {event_id} references "
                    f"unknown customer {customer_id}"
                )

    def validate_purchase_events(self, orders, events):
        """
        Ensures every purchase event references a valid order
        and matches the customer attached to that order.
        """

        for event_id, event in events.items():

            if event.get("event_type") != "purchase":
                continue

            order_id = event.get("order_id")
            customer_id = event.get("customer_id")

            if order_id not in orders:
                self.add_error(
                    f"Purchase event {event_id} references "
                    f"unknown order {order_id}"
                )
                continue

            order = orders[order_id]

            order_customer_id = order.get("customer_id")

            if customer_id != order_customer_id:
                self.add_error(
                    f"Purchase event {event_id} customer "
                    f"{customer_id} does not match order "
                    f"{order_id} customer {order_customer_id}"
                )

    def validate_record_ids(self, records, id_field, record_type):
        """
        Ensures the ID inside each record matches
        the dictionary key used to store that record.
        """

        for record_key, record in records.items():

            record_id = record.get(id_field)

            # Some records may rely only on the dictionary key.
            if record_id is None:
                continue

            if record_id != record_key:
                self.add_error(
                    f"{record_type} key {record_key} does not match "
                    f"{id_field} {record_id}"
                )

    def validate_customer_lifetime_orders(self, customers, orders):
        """
        Ensures each customer's lifetime_orders matches
        the actual number of orders belonging to that customer.
        """

        actual_order_counts = {}

        for order in orders.values():

            customer_id = order.get("customer_id")

            actual_order_counts[customer_id] = (
                actual_order_counts.get(customer_id, 0) + 1
            )

        for customer_id, customer in customers.items():

            expected_count = customer.get(
                "lifetime_orders",
                0
            )

            actual_count = actual_order_counts.get(
                customer_id,
                0
            )

            if expected_count != actual_count:
                self.add_error(
                    f"Customer {customer_id} lifetime_orders "
                    f"is {expected_count}, but actual order "
                    f"count is {actual_count}"
                )                                    

    def validate_customer_lifetime_spend(self, customers, orders):
        """
        Ensures each customer's lifetime_spend matches
        the sum of gross_amount from their orders.
        """

        actual_spend = {}

        for order in orders.values():

            customer_id = order.get("customer_id")
            gross_amount = order.get("gross_amount", 0)

            actual_spend[customer_id] = (
                actual_spend.get(customer_id, 0) + gross_amount
            )

        for customer_id, customer in customers.items():

            expected_spend = customer.get(
                "lifetime_spend",
                0
            )

            actual_total = actual_spend.get(
                customer_id,
                0
            )

            if expected_spend != actual_total:
                self.add_error(
                    f"Customer {customer_id} lifetime_spend "
                    f"is {expected_spend}, but actual order "
                    f"spend is {actual_total}"
                )

    def validate_customer_last_order_day(self, customers, orders):
        """
        Ensures each customer's last_order_day matches
        the latest simulation_day among their orders.
        """

        latest_order_day = {}

        for order in orders.values():
            customer_id = order.get("customer_id")
            simulation_day = order.get("simulation_day")

            if simulation_day is None:
                continue

            if (
                customer_id not in latest_order_day
                or simulation_day > latest_order_day[customer_id]
            ):
                latest_order_day[customer_id] = simulation_day

        for customer_id, customer in customers.items():

            expected_day = customer.get(
                "last_order_day"
            )

            actual_day = latest_order_day.get(
                customer_id
            )

            if expected_day != actual_day:
                self.add_error(
                    f"Customer {customer_id} last_order_day "
                    f"is {expected_day}, but latest actual "
                    f"order day is {actual_day}"
                )

    def validate_daily_order_counts(self, daily_metrics, orders):
        """
        Ensures daily_metrics valid order counts match
        the actual number of stored orders for each simulation day.
        """

        actual_orders_by_day = {}

        for order in orders.values():
            day = order.get("simulation_day")

            if day is None:
                continue

            actual_orders_by_day[day] = (
                actual_orders_by_day.get(day, 0) + 1
            )

        for metric in daily_metrics:

            day = metric.get("simulation_day")

            order_metrics = metric.get(
                "orders",
                {}
            )

            expected_orders = order_metrics.get(
                "valid_orders",
                0
            )

            actual_orders = actual_orders_by_day.get(
                day,
                0
            )

            if expected_orders != actual_orders:
                self.add_error(
                    f"Day {day} metrics reports "
                    f"{expected_orders} valid orders, but actual "
                    f"stored order count is {actual_orders}"
                )

    def validate_daily_event_counts(self, daily_metrics, events):
        """
        Ensures daily_metrics event counts match
        the actual number of stored events for each simulation day.
        """

        actual_events_by_day = {}

        for event in events.values():
            day = event.get("simulation_day")

            if day is None:
                continue

            actual_events_by_day[day] = (
                actual_events_by_day.get(day, 0) + 1
            )

        for metric in daily_metrics:

            day = metric.get("simulation_day")

            behavior_metrics = metric.get(
                "behavior_events",
                {}
            )

            behavior_events = behavior_metrics.get(
                "total_events",
                0
            )

            purchase_events = metric.get(
                "purchase_events",
                0
            )

            expected_events = (
                behavior_events + purchase_events
            )

            actual_events = actual_events_by_day.get(
                day,
                0
            )

            if expected_events != actual_events:
                self.add_error(
                    f"Day {day} metrics reports "
                    f"{expected_events} total events, but actual "
                    f"event count is {actual_events}"
                )

    def validate_counters(self, counters, customers, orders, events):
        """
        Ensures SimulationState counters match
        the actual number of stored records.
        """

        expected_counts = {
            "customer": len(customers),
            "order": len(orders),
            "event": len(events),
        }

        for counter_name, expected_count in expected_counts.items():

            actual_count = counters.get(
                counter_name,
                0
            )

            if actual_count != expected_count:
                self.add_error(
                    f"Counter '{counter_name}' is {actual_count}, "
                    f"but actual record count is {expected_count}"
                )                                

    def validate_all(
        self,
        customers,
        orders,
        events,
        daily_metrics,
        counters
    ):
        """
        Runs all cross-table validation checks.
        """

        # Clear previous validation errors
        self.errors.clear()

        self.validate_order_customers(
            customers,
            orders
        )

        self.validate_event_customers(
            customers,
            events
        )

        self.validate_purchase_events(
            orders,
            events
        )

        self.validate_record_ids(
            customers,
            "customer_id",
            "Customer"
        )

        self.validate_record_ids(
            orders,
            "order_id",
            "Order"
        )

        self.validate_record_ids(
            events,
            "event_id",
            "Event"
        )

        self.validate_customer_lifetime_orders(
            customers,
            orders
        )

        self.validate_customer_lifetime_spend(
            customers,
            orders
        )

        self.validate_customer_last_order_day(
            customers,
            orders
        )

        self.validate_daily_order_counts(
            daily_metrics,
            orders
        )

        self.validate_daily_event_counts(
            daily_metrics,
            events
        )

        self.validate_counters(
            counters,
            customers,
            orders,
            events
        )

        return self.summary()

if __name__ == "__main__":

        validator = CrossTableValidator()

        customers = {
            "CUST001": {
                "customer_id": "CUST001",
                "name": "Customer One",
                "lifetime_orders": 2,
                "lifetime_spend": 140.0,
                "last_order_day": 3
            },
            "CUST002": {
                "customer_id": "CUST002",
                "name": "Customer Two",
                "lifetime_orders": 1,
                "lifetime_spend": 50.0,
                "last_order_day": 2
            }
        }

        orders = {
            "ORD001": {
                "order_id": "ORD001",
                "customer_id": "CUST001",
                "gross_amount": 100.0,
                "simulation_day": 1
            },
            "ORD003": {
                "order_id": "ORD003",
                "customer_id": "CUST001",
                "gross_amount": 40.0,
                "simulation_day": 3
            },
            "ORD002": {
                "order_id": "ORD002",
                "customer_id": "CUST002",
                "gross_amount": 50.0,
                "simulation_day": 2
            }
        }

        events = {
            "EVT001": {
                "event_id": "EVT001",
                "customer_id": "CUST001",
                "event_type": "purchase",
                "order_id": "ORD001",
                "simulation_day": 1
            },
            "EVT002": {
                "event_id": "EVT002",
                "customer_id": "CUST002",
                "event_type": "product_view",
                "simulation_day": 2
            }
        }

        daily_metrics = [
            {
                "day": 1,
                "orders": 1,
                "events": 1
            },
            {
                "day": 2,
                "orders": 1,
                "events": 1
            },
            {
                "day": 3,
                "orders": 1,
                "events": 0
            }
        ]

        counters = {
            "customer": 2,
            "order": 3,
            "event": 2
        }

        result = validator.validate_all(
            customers=customers,
            orders=orders,
            events=events,
            daily_metrics=daily_metrics,
            counters=counters
        )

        print("=" * 60)
        print("CROSS-TABLE VALIDATOR TEST")
        print("=" * 60)

        print(result)

        # validator.validate_event_customers(
        #     customers,
        #     events
        # )

        # validator.validate_purchase_events(
        #     orders,
        #     events
        # )

        # validator.validate_record_ids(
        #     orders,
        #     "order_id",
        #     "Order"
        # )

        # validator.validate_record_ids(
        #     customers,
        #     "customer_id",
        #     "Customer"
        # )

        # validator.validate_record_ids(
        #     orders,
        #     "order_id",
        #     "Order"
        # )

        # validator.validate_record_ids(
        #     events,
        #     "event_id",
        #     "Event"
        # )

        # validator.validate_customer_lifetime_orders(
        #     customers,
        #     orders
        # )

        # validator.validate_customer_lifetime_spend(
        #     customers,
        #     orders
        # )

        # validator.validate_customer_last_order_day(
        #     customers,
        #     orders
        # )

        # validator.validate_daily_order_counts(
        #     daily_metrics,
        #     orders
        # )

        # validator.validate_daily_event_counts(
        #     daily_metrics,
        #     events
        # )

        # validator.validate_counters(
        #     counters,
        #     customers,
        #     orders,
        #     events
        # )

        # print("=" * 60)
        # print("CROSS-TABLE VALIDATOR TEST")
        # print("=" * 60)

        # print(validator.summary())