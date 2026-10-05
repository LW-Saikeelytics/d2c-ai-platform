class BusinessRuleValidator:

    def __init__(self, simulation_state):
        self.state = simulation_state

        self.errors = []
        self.warnings = []
        self.checks = {}

    # ============================================================
    # ORDER AMOUNT CONSISTENCY
    # ============================================================

    def validate_order_amounts(self):

        invalid_order_amounts = 0

        for order_id, order in self.state.orders.items():

            quantity = order.get("quantity")
            unit_price = order.get("unit_price")
            gross_amount = order.get("gross_amount")

            # Structural validation is handled by
            # DatasetQualityValidator, so skip incomplete records here.
            if (
                quantity is None
                or unit_price is None
                or gross_amount is None
            ):
                continue

            expected_amount = quantity * unit_price

            if abs(gross_amount - expected_amount) > 0.01:

                invalid_order_amounts += 1

                self.errors.append(
                    f"Order '{order_id}' has gross_amount "
                    f"'{gross_amount}', expected '{expected_amount}'."
                )

        self.checks["order_amount_consistency"] = {
            "invalid_order_amounts": invalid_order_amounts
        }

    # ============================================================
    # CUSTOMER LIFETIME ORDER CONSISTENCY
    # ============================================================

    def validate_customer_lifetime_orders(self):

        inconsistent_customers = 0

        # Count actual orders per customer
        actual_order_counts = {}

        for order in self.state.orders.values():

            customer_id = order.get("customer_id")

            if customer_id is None:
                continue

            actual_order_counts[customer_id] = (
                actual_order_counts.get(customer_id, 0) + 1
            )

        # Compare against customer lifetime_orders
        for customer_id, customer in self.state.customers.items():

            lifetime_orders = customer.get("lifetime_orders")

            if lifetime_orders is None:
                continue

            actual_orders = actual_order_counts.get(
                customer_id,
                0
            )

            if lifetime_orders != actual_orders:

                inconsistent_customers += 1

                self.errors.append(
                    f"Customer '{customer_id}' has "
                    f"lifetime_orders '{lifetime_orders}', "
                    f"but actual order count is '{actual_orders}'."
                )

        self.checks["customer_lifetime_orders"] = {
            "inconsistent_customers": inconsistent_customers
        }

    # ============================================================
    # CUSTOMER LIFETIME SPEND CONSISTENCY
    # ============================================================

    def validate_customer_lifetime_spend(self):

        inconsistent_customers = 0

        actual_spend = {}

        # --------------------------------------------------------
        # CALCULATE ACTUAL SPEND FROM ORDERS
        # --------------------------------------------------------

        for order in self.state.orders.values():

            customer_id = order.get("customer_id")
            gross_amount = order.get("gross_amount")

            if (
                customer_id is None
                or gross_amount is None
            ):
                continue

            actual_spend[customer_id] = (
                actual_spend.get(customer_id, 0.0)
                + gross_amount
            )

        # --------------------------------------------------------
        # COMPARE WITH CUSTOMER STATE
        # --------------------------------------------------------

        for customer_id, customer in self.state.customers.items():

            lifetime_spend = customer.get("lifetime_spend")

            if lifetime_spend is None:
                continue

            expected_spend = actual_spend.get(
                customer_id,
                0.0
            )

            if abs(lifetime_spend - expected_spend) > 0.01:

                inconsistent_customers += 1

                self.errors.append(
                    f"Customer '{customer_id}' has "
                    f"lifetime_spend '{lifetime_spend}', "
                    f"but actual order spend is '{expected_spend}'."
                )

        self.checks["customer_lifetime_spend"] = {
            "inconsistent_customers": inconsistent_customers
        }

    # ============================================================
    # CUSTOMER LAST ORDER DAY CONSISTENCY
    # ============================================================

    def validate_customer_last_order_day(self):

        inconsistent_customers = 0

        actual_last_order_days = {}

        # --------------------------------------------------------
        # FIND ACTUAL LAST ORDER DAY
        # --------------------------------------------------------

        for order in self.state.orders.values():

            customer_id = order.get("customer_id")
            simulation_day = order.get("simulation_day")

            if (
                customer_id is None
                or simulation_day is None
            ):
                continue

            if customer_id not in actual_last_order_days:
                actual_last_order_days[customer_id] = simulation_day

            else:
                actual_last_order_days[customer_id] = max(
                    actual_last_order_days[customer_id],
                    simulation_day
                )

        # --------------------------------------------------------
        # COMPARE WITH CUSTOMER STATE
        # --------------------------------------------------------

        for customer_id, customer in self.state.customers.items():

            lifetime_orders = customer.get("lifetime_orders", 0)
            last_order_day = customer.get("last_order_day")

            # Customer has no orders
            if lifetime_orders == 0:

                if last_order_day is not None:
                    inconsistent_customers += 1

                    self.errors.append(
                        f"Customer '{customer_id}' has no orders "
                        f"but last_order_day is '{last_order_day}'."
                    )

                continue

            expected_last_order_day = actual_last_order_days.get(
                customer_id
            )

            if last_order_day != expected_last_order_day:

                inconsistent_customers += 1

                self.errors.append(
                    f"Customer '{customer_id}' has "
                    f"last_order_day '{last_order_day}', "
                    f"but actual last order day is "
                    f"'{expected_last_order_day}'."
                )

        self.checks["customer_last_order_day"] = {
            "inconsistent_customers": inconsistent_customers
        }

    # ============================================================
    # PURCHASE EVENT <-> ORDER CONSISTENCY
    # ============================================================

    def validate_purchase_event_order_consistency(self):

        missing_order_ids = 0
        unknown_order_refs = 0
        field_mismatches = 0
        orders_without_purchase_event = 0
        orders_with_multiple_purchase_events = 0

        purchase_events_by_order = {}

        # --------------------------------------------------------
        # VALIDATE PURCHASE EVENTS
        # --------------------------------------------------------

        for event_id, event in self.state.events.items():

            if event.get("event_type") != "purchase":
                continue

            order_id = event.get("order_id")

            # Purchase events must reference an order
            if order_id is None:

                missing_order_ids += 1

                self.errors.append(
                    f"Purchase event '{event_id}' "
                    f"does not contain an order_id."
                )

                continue

            # Track purchase events for each order
            purchase_events_by_order.setdefault(
                order_id,
                []
            ).append(event_id)

            # Referenced order must exist
            order = self.state.orders.get(order_id)

            if order is None:

                unknown_order_refs += 1

                self.errors.append(
                    f"Purchase event '{event_id}' references "
                    f"unknown order_id '{order_id}'."
                )

                continue

            # ----------------------------------------------------
            # FIELD CONSISTENCY
            # ----------------------------------------------------

            fields_to_compare = [
                "customer_id",
                "simulation_day",
                "product_id",
                "category"
            ]

            for field in fields_to_compare:

                event_value = event.get(field)
                order_value = order.get(field)

                if event_value != order_value:

                    field_mismatches += 1

                    self.errors.append(
                        f"Purchase event '{event_id}' field "
                        f"'{field}' is '{event_value}', "
                        f"but order '{order_id}' has "
                        f"'{order_value}'."
                    )

        # --------------------------------------------------------
        # VALIDATE EVERY ORDER HAS EXACTLY ONE PURCHASE EVENT
        # --------------------------------------------------------

        for order_id in self.state.orders:

            purchase_event_ids = purchase_events_by_order.get(
                order_id,
                []
            )

            if len(purchase_event_ids) == 0:

                orders_without_purchase_event += 1

                self.errors.append(
                    f"Order '{order_id}' has no matching "
                    f"purchase event."
                )

            elif len(purchase_event_ids) > 1:

                orders_with_multiple_purchase_events += 1

                self.errors.append(
                    f"Order '{order_id}' has multiple purchase "
                    f"events: {purchase_event_ids}."
                )

        # --------------------------------------------------------
        # RESULTS
        # --------------------------------------------------------

        self.checks["purchase_event_order_consistency"] = {
            "missing_order_ids": missing_order_ids,
            "unknown_order_refs": unknown_order_refs,
            "field_mismatches": field_mismatches,
            "orders_without_purchase_event": orders_without_purchase_event,
            "orders_with_multiple_purchase_events": (
                orders_with_multiple_purchase_events
            )
        }

    # ============================================================
    # EVENT-SPECIFIC BUSINESS RULES
    # ============================================================

    def validate_event_specific_rules(self):

        invalid_events = 0

        for event_id, event in self.state.events.items():

            event_type = event.get("event_type")

            # ----------------------------------------------------
            # PRODUCT VIEW
            # ----------------------------------------------------

            if event_type == "product_view":

                if event.get("product_id") is None:
                    invalid_events += 1

                    self.errors.append(
                        f"Product view event '{event_id}' "
                        f"is missing product_id."
                    )

                if event.get("category") is None:
                    invalid_events += 1

                    self.errors.append(
                        f"Product view event '{event_id}' "
                        f"is missing category."
                    )

            # ----------------------------------------------------
            # PURCHASE
            # ----------------------------------------------------

            elif event_type == "purchase":

                if event.get("order_id") is None:
                    invalid_events += 1

                    self.errors.append(
                        f"Purchase event '{event_id}' "
                        f"is missing order_id."
                    )

                if event.get("product_id") is None:
                    invalid_events += 1

                    self.errors.append(
                        f"Purchase event '{event_id}' "
                        f"is missing product_id."
                    )

                if event.get("category") is None:
                    invalid_events += 1

                    self.errors.append(
                        f"Purchase event '{event_id}' "
                        f"is missing category."
                    )

        self.checks["event_specific_rules"] = {
            "invalid_events": invalid_events
        }

    # ============================================================
    # MAIN VALIDATION
    # ============================================================

    def validate_all(self):

        self.errors = []
        self.warnings = []
        self.checks = {}

        self.validate_order_amounts()
        self.validate_customer_lifetime_orders()
        self.validate_customer_lifetime_spend()
        self.validate_customer_last_order_day()
        self.validate_purchase_event_order_consistency()
        self.validate_event_specific_rules()

        return {
            "passed": len(self.errors) == 0,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
            "checks": self.checks
        }