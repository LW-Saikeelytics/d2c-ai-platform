class CategoricalValueValidator:

    def __init__(self, config, state):
        self.config = config
        self.state = state

        self.errors = []
        self.checks = {}

        # --------------------------------------------------
        # MASTER-DATA LOOKUPS
        # --------------------------------------------------

        self.segment_ids = {
            item["segment_id"]
            for item in config["customer_segments"]
        }

        self.city_ids = {
            item["city_id"]
            for item in config["cities"]
        }

        self.regions = {
            item["region"]
            for item in config["cities"]
        }

        self.channel_ids = {
            item["channel_id"]
            for item in config["channels"]
        }

        self.product_ids = {
            item["product_id"]
            for item in config["products"]
        }

        self.variant_ids = {
            item["variant_id"]
            for item in config["variants"]
        }

        self.categories = {
            item.get("category")
            for item in config["products"]
            if item.get("category") is not None
        }

        self.subcategories = {
            item.get("subcategory")
            for item in config["products"]
            if item.get("subcategory") is not None
        }

        self.tendency_values = {
            "low",
            "medium",
            "high"
        }

        self.event_types = {
            "product_view",
            "add_to_cart",
            "cart_abandonment",
            "purchase_intent",
            "purchase"
        }

        self.behavior_profiles = set(
            self.config["company"]
            .get(
                "behavior_profiles",
                {}
            )
            .keys()
        )

    # --------------------------------------------------
    # HELPER
    # --------------------------------------------------

    def _check_allowed(
        self,
        value,
        allowed_values,
        field_path
    ):

        if value not in allowed_values:
            self.errors.append(
                f"{field_path}: invalid value "
                f"{value!r}"
            )

    # --------------------------------------------------
    # CUSTOMERS
    # --------------------------------------------------

    def validate_customers(self):

        start_errors = len(self.errors)

        for customer_id, customer in self.state.customers.items():

            prefix = f"customers[{customer_id}]"

            self._check_allowed(
                customer.get("segment"),
                self.segment_ids,
                f"{prefix}.segment"
            )

            self._check_allowed(
                customer.get("city_id"),
                self.city_ids,
                f"{prefix}.city_id"
            )

            self._check_allowed(
                customer.get("region"),
                self.regions,
                f"{prefix}.region"
            )

            self._check_allowed(
                customer.get("acquisition_channel"),
                self.channel_ids,
                f"{prefix}.acquisition_channel"
            )

            for field_name in [
                "price_tendency",
                "discount_sensitivity",
                "premium_product_tendency",
                "repeat_purchase_tendency"
            ]:

                self._check_allowed(
                    customer.get(field_name),
                    self.tendency_values,
                    f"{prefix}.{field_name}"
                )

            preferred_categories = customer.get(
                "preferred_categories",
                []
            )

            for category in preferred_categories:

                self._check_allowed(
                    category,
                    self.categories,
                    f"{prefix}.preferred_categories"
                )

            self._check_allowed(
                customer.get(
                    "behavior_profile"
                ),
                self.behavior_profiles,
                f"{prefix}.behavior_profile"
            )

        error_count = (
            len(self.errors)
            - start_errors
        )

        self.checks["customers"] = {
            "records_checked": len(
                self.state.customers
            ),
            "errors": error_count,
            "passed": error_count == 0
        }

    # --------------------------------------------------
    # ORDERS
    # --------------------------------------------------

    def validate_orders(self):

        start_errors = len(self.errors)

        for order_id, order in self.state.orders.items():

            prefix = f"orders[{order_id}]"

            checks = [
                (
                    "segment",
                    self.segment_ids
                ),
                (
                    "city_id",
                    self.city_ids
                ),
                (
                    "region",
                    self.regions
                ),
                (
                    "channel",
                    self.channel_ids
                ),
                (
                    "product_id",
                    self.product_ids
                ),
                (
                    "variant_id",
                    self.variant_ids
                ),
                (
                    "category",
                    self.categories
                ),
                (
                    "subcategory",
                    self.subcategories
                )
            ]

            for field_name, allowed_values in checks:

                self._check_allowed(
                    order.get(field_name),
                    allowed_values,
                    f"{prefix}.{field_name}"
                )

        error_count = (
            len(self.errors)
            - start_errors
        )

        self.checks["orders"] = {
            "records_checked": len(
                self.state.orders
            ),
            "errors": error_count,
            "passed": error_count == 0
        }

    # --------------------------------------------------
    # EVENTS
    # --------------------------------------------------

    def _validate_event_record(
        self,
        event,
        prefix
    ):

        self._check_allowed(
            event.get("event_type"),
            self.event_types,
            f"{prefix}.event_type"
        )

        product_id = event.get(
            "product_id"
        )

        if product_id is not None:

            self._check_allowed(
                product_id,
                self.product_ids,
                f"{prefix}.product_id"
            )

        category = event.get(
            "category"
        )

        if category is not None:

            self._check_allowed(
                category,
                self.categories,
                f"{prefix}.category"
            )

    def validate_events(self):

        start_errors = len(self.errors)

        for event_id, event in self.state.events.items():

            self._validate_event_record(
                event,
                f"events[{event_id}]"
            )

        error_count = (
            len(self.errors)
            - start_errors
        )

        self.checks["events"] = {
            "records_checked": len(
                self.state.events
            ),
            "errors": error_count,
            "passed": error_count == 0
        }

    # --------------------------------------------------
    # BEHAVIOR HISTORY
    # --------------------------------------------------

    def validate_behavior_history(self):

        start_errors = len(self.errors)

        for index, event in enumerate(
            self.state.behavior_history
        ):

            self._validate_event_record(
                event,
                f"behavior_history[{index}]"
            )

        error_count = (
            len(self.errors)
            - start_errors
        )

        self.checks["behavior_history"] = {
            "records_checked": len(
                self.state.behavior_history
            ),
            "errors": error_count,
            "passed": error_count == 0
        }

    # --------------------------------------------------
    # CONVERSION HISTORY
    # --------------------------------------------------

    def validate_conversion_history(self):

        start_errors = len(self.errors)

        for index, record in enumerate(
            self.state.conversion_history
        ):

            product_id = (
                record
                .get("result", {})
                .get("product_id")
            )

            if product_id is not None:

                self._check_allowed(
                    product_id,
                    self.product_ids,
                    (
                        f"conversion_history"
                        f"[{index}]"
                        f".result.product_id"
                    )
                )

        error_count = (
            len(self.errors)
            - start_errors
        )

        self.checks["conversion_history"] = {
            "records_checked": len(
                self.state.conversion_history
            ),
            "errors": error_count,
            "passed": error_count == 0
        }

    # --------------------------------------------------
    # COMPLETE VALIDATION
    # --------------------------------------------------

    def validate_all(self):

        self.errors = []
        self.checks = {}

        self.validate_customers()
        self.validate_orders()
        self.validate_events()
        self.validate_behavior_history()
        self.validate_conversion_history()

        return {
            "passed": len(self.errors) == 0,
            "error_count": len(
                self.errors
            ),
            "errors": self.errors,
            "checks": self.checks
        }