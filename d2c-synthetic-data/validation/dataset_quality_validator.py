class DatasetQualityValidator:

    def __init__(self, simulation_state):
        self.state = simulation_state

        self.errors = []
        self.warnings = []
        self.checks = {}

    # ============================================================
    # RECORD COUNT CHECKS
    # ============================================================

    def validate_record_counts(self):

        customer_count = len(self.state.customers)
        order_count = len(self.state.orders)
        event_count = len(self.state.events)

        self.checks["record_counts"] = {
            "customers": customer_count,
            "orders": order_count,
            "events": event_count
        }

        # Customers are required for a meaningful simulation
        if customer_count == 0:
            self.errors.append(
                "Dataset contains no customer records."
            )

        # Orders and events may legitimately be zero,
        # especially during early simulation days.

    # ============================================================
    # MAIN VALIDATION
    # ============================================================

    def validate_all(self):

        # Reset previous validation results
        self.errors = []
        self.warnings = []
        self.checks = {}

        self.validate_record_counts()
        self.validate_required_fields()
        self.validate_duplicate_ids()
        self.validate_foreign_keys()
        self.validate_value_ranges()

        return {
            "passed": len(self.errors) == 0,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
            "checks": self.checks
        }

    # ============================================================
    # DUPLICATE ID CHECKS
    # ============================================================

    def validate_duplicate_ids(self):

        duplicate_customers = 0
        duplicate_orders = 0
        duplicate_events = 0

        key_mismatches = 0

        # --------------------------------------------------------
        # CUSTOMERS
        # --------------------------------------------------------

        customer_ids = []

        for key, customer in self.state.customers.items():

            customer_id = customer.get("customer_id")

            if customer_id is not None:
                customer_ids.append(customer_id)

                if key != customer_id:
                    key_mismatches += 1

                    self.errors.append(
                        f"Customer dictionary key '{key}' "
                        f"does not match customer_id '{customer_id}'."
                    )

        duplicate_customers = (
            len(customer_ids) - len(set(customer_ids))
        )

        if duplicate_customers > 0:
            self.errors.append(
                f"Found {duplicate_customers} duplicate customer IDs."
            )

        # --------------------------------------------------------
        # ORDERS
        # --------------------------------------------------------

        order_ids = []

        for key, order in self.state.orders.items():

            order_id = order.get("order_id")

            if order_id is not None:
                order_ids.append(order_id)

                if key != order_id:
                    key_mismatches += 1

                    self.errors.append(
                        f"Order dictionary key '{key}' "
                        f"does not match order_id '{order_id}'."
                    )

        duplicate_orders = (
            len(order_ids) - len(set(order_ids))
        )

        if duplicate_orders > 0:
            self.errors.append(
                f"Found {duplicate_orders} duplicate order IDs."
            )

        # --------------------------------------------------------
        # EVENTS
        # --------------------------------------------------------

        event_ids = []

        for key, event in self.state.events.items():

            event_id = event.get("event_id")

            if event_id is not None:
                event_ids.append(event_id)

                if key != event_id:
                    key_mismatches += 1

                    self.errors.append(
                        f"Event dictionary key '{key}' "
                        f"does not match event_id '{event_id}'."
                    )

        duplicate_events = (
            len(event_ids) - len(set(event_ids))
        )

        if duplicate_events > 0:
            self.errors.append(
                f"Found {duplicate_events} duplicate event IDs."
            )

        # --------------------------------------------------------
        # RESULTS
        # --------------------------------------------------------

        self.checks["duplicate_ids"] = {
            "duplicate_customer_ids": duplicate_customers,
            "duplicate_order_ids": duplicate_orders,
            "duplicate_event_ids": duplicate_events,
            "key_id_mismatches": key_mismatches
        }

    # ============================================================
    # FOREIGN KEY CHECKS
    # ============================================================

    def validate_foreign_keys(self):

        invalid_order_customers = 0
        invalid_event_customers = 0

        customer_ids = set(self.state.customers.keys())

        # --------------------------------------------------------
        # ORDER -> CUSTOMER
        # --------------------------------------------------------

        for order_id, order in self.state.orders.items():

            customer_id = order.get("customer_id")

            if customer_id is None:
                continue

            if customer_id not in customer_ids:
                invalid_order_customers += 1

                self.errors.append(
                    f"Order '{order_id}' references unknown "
                    f"customer_id '{customer_id}'."
                )

        # --------------------------------------------------------
        # EVENT -> CUSTOMER
        # --------------------------------------------------------

        for event_id, event in self.state.events.items():

            customer_id = event.get("customer_id")

            if customer_id is None:
                continue

            if customer_id not in customer_ids:
                invalid_event_customers += 1

                self.errors.append(
                    f"Event '{event_id}' references unknown "
                    f"customer_id '{customer_id}'."
                )

        # --------------------------------------------------------
        # RESULTS
        # --------------------------------------------------------

        self.checks["foreign_keys"] = {
            "invalid_order_customer_refs": invalid_order_customers,
            "invalid_event_customer_refs": invalid_event_customers
        }

    # ============================================================
    # BASIC VALUE / RANGE CHECKS
    # ============================================================

    def validate_value_ranges(self):

        invalid_customer_values = 0
        invalid_order_values = 0
        invalid_event_values = 0

        current_day = self.state.current_day

        # --------------------------------------------------------
        # CUSTOMERS
        # --------------------------------------------------------

        for customer_id, customer in self.state.customers.items():

            lifetime_orders = customer.get("lifetime_orders")

            if (
                lifetime_orders is not None
                and (
                    not isinstance(lifetime_orders, int)
                    or isinstance(lifetime_orders, bool)
                    or lifetime_orders < 0
                )
            ):
                invalid_customer_values += 1
                self.errors.append(
                    f"Customer '{customer_id}' has invalid "
                    f"lifetime_orders '{lifetime_orders}'."
                )

            lifetime_spend = customer.get("lifetime_spend")

            if (
                lifetime_spend is not None
                and (
                    not isinstance(lifetime_spend, (int, float))
                    or isinstance(lifetime_spend, bool)
                    or lifetime_spend < 0
                )
            ):
                invalid_customer_values += 1
                self.errors.append(
                    f"Customer '{customer_id}' has invalid "
                    f"lifetime_spend '{lifetime_spend}'."
                )

            purchase_propensity = customer.get("purchase_propensity")

            if (
                purchase_propensity is not None
                and (
                    not isinstance(purchase_propensity, (int, float))
                    or isinstance(purchase_propensity, bool)
                    or not 0 <= purchase_propensity <= 1
                )
            ):
                invalid_customer_values += 1
                self.errors.append(
                    f"Customer '{customer_id}' has invalid "
                    f"purchase_propensity '{purchase_propensity}'."
                )

            registration_day = customer.get("registration_day")

            if (
                registration_day is not None
                and (
                    not isinstance(registration_day, int)
                    or isinstance(registration_day, bool)
                    or registration_day > current_day
                )
            ):
                invalid_customer_values += 1
                self.errors.append(
                    f"Customer '{customer_id}' has invalid "
                    f"registration_day '{registration_day}'."
                )

        # --------------------------------------------------------
        # ORDERS
        # --------------------------------------------------------

        for order_id, order in self.state.orders.items():

            simulation_day = order.get("simulation_day")

            if (
                simulation_day is not None
                and (
                    not isinstance(simulation_day, int)
                    or isinstance(simulation_day, bool)
                    or simulation_day < 1
                    or simulation_day > current_day
                )
            ):
                invalid_order_values += 1
                self.errors.append(
                    f"Order '{order_id}' has invalid "
                    f"simulation_day '{simulation_day}'."
                )

            quantity = order.get("quantity")

            if (
                quantity is not None
                and (
                    not isinstance(quantity, int)
                    or isinstance(quantity, bool)
                    or quantity <= 0
                )
            ):
                invalid_order_values += 1
                self.errors.append(
                    f"Order '{order_id}' has invalid "
                    f"quantity '{quantity}'."
                )

            unit_price = order.get("unit_price")

            if (
                unit_price is not None
                and (
                    not isinstance(unit_price, (int, float))
                    or isinstance(unit_price, bool)
                    or unit_price < 0
                )
            ):
                invalid_order_values += 1
                self.errors.append(
                    f"Order '{order_id}' has invalid "
                    f"unit_price '{unit_price}'."
                )

            gross_amount = order.get("gross_amount")

            if (
                gross_amount is not None
                and (
                    not isinstance(gross_amount, (int, float))
                    or isinstance(gross_amount, bool)
                    or gross_amount < 0
                )
            ):
                invalid_order_values += 1
                self.errors.append(
                    f"Order '{order_id}' has invalid "
                    f"gross_amount '{gross_amount}'."
                )

        # --------------------------------------------------------
        # EVENTS
        # --------------------------------------------------------

        for event_id, event in self.state.events.items():

            simulation_day = event.get("simulation_day")

            if (
                simulation_day is not None
                and (
                    not isinstance(simulation_day, int)
                    or isinstance(simulation_day, bool)
                    or simulation_day < 1
                    or simulation_day > current_day
                )
            ):
                invalid_event_values += 1
                self.errors.append(
                    f"Event '{event_id}' has invalid "
                    f"simulation_day '{simulation_day}'."
                )

        # --------------------------------------------------------
        # RESULTS
        # --------------------------------------------------------

        self.checks["value_ranges"] = {
            "invalid_customer_values": invalid_customer_values,
            "invalid_order_values": invalid_order_values,
            "invalid_event_values": invalid_event_values
        }

    # ============================================================
    # REQUIRED FIELD CHECKS
    # ============================================================

    def validate_required_fields(self):

        required_customer_fields = [
            "customer_id",
            "segment",
            "city_id",
            "region",
            "acquisition_channel",
            "registration_day",
            "lifetime_orders",
            "lifetime_spend",
            "purchase_propensity",
            "status"
        ]

        required_order_fields = [
            "order_id",
            "simulation_day",
            "customer_id",
            "segment",
            "city_id",
            "region",
            "channel",
            "product_id",
            "variant_id",
            "category",
            "subcategory",
            "quantity",
            "unit_price",
            "gross_amount"
        ]

        required_event_fields = [
            "event_id",
            "simulation_day",
            "customer_id",
            "event_type"
        ]

        customer_missing = 0
        order_missing = 0
        event_missing = 0

        # --------------------------------------------------------
        # CUSTOMERS
        # --------------------------------------------------------

        for customer_id, customer in self.state.customers.items():

            for field in required_customer_fields:

                if field not in customer:
                    customer_missing += 1

                    self.errors.append(
                        f"Customer '{customer_id}' missing required field '{field}'."
                    )

        # --------------------------------------------------------
        # ORDERS
        # --------------------------------------------------------

        for order_id, order in self.state.orders.items():

            for field in required_order_fields:

                if field not in order:
                    order_missing += 1

                    self.errors.append(
                        f"Order '{order_id}' missing required field '{field}'."
                    )

        # --------------------------------------------------------
        # EVENTS
        # --------------------------------------------------------

        for event_id, event in self.state.events.items():

            for field in required_event_fields:

                if field not in event:
                    event_missing += 1

                    self.errors.append(
                        f"Event '{event_id}' missing required field '{field}'."
                    )

        self.checks["required_fields"] = {
            "customer_missing_fields": customer_missing,
            "order_missing_fields": order_missing,
            "event_missing_fields": event_missing
        }