class OrderValidator:

    def __init__(self, config):
        self.config = config

        self.products = {
            p["product_id"]: p
            for p in config["products"]
        }

        self.variants = {
            v["variant_id"]: v
            for v in config["variants"]
        }

        self.cities = {
            c["city_id"]: c
            for c in config["cities"]
        }

        self.segments = {
            s["segment_id"]: s
            for s in config["customer_segments"]
        }

        self.channels = {
            c["channel_id"]: c
            for c in config["channels"]
        }

    def validate(self, order, customer):

        errors = []

        # -------------------------------------------------
        # BASIC ORDER FIELDS
        # -------------------------------------------------

        if not order.get("order_id"):
            errors.append("Missing order_id")

        if not order.get("customer_id"):
            errors.append("Missing customer_id")

        if order.get("customer_id") != customer.get("customer_id"):
            errors.append("Order customer does not match supplied customer")

        if not order.get("simulation_day"):
            errors.append("Missing simulation_day")

        # -------------------------------------------------
        # CUSTOMER
        # -------------------------------------------------

        customer_id = order.get("customer_id")

        if customer_id != customer.get("customer_id"):
            errors.append("Invalid customer reference")

        segment_id = order.get("segment")

        if segment_id not in self.segments:
            errors.append(
                f"Invalid customer segment: {segment_id}"
            )

        # -------------------------------------------------
        # CITY / REGION
        # -------------------------------------------------

        city_id = order.get("city_id")

        if city_id not in self.cities:
            errors.append(
                f"Invalid city: {city_id}"
            )
        else:
            expected_region = self.cities[city_id].get("region")

            if order.get("region") != expected_region:
                errors.append(
                    f"Region mismatch for city {city_id}"
                )

        # -------------------------------------------------
        # CHANNEL
        # -------------------------------------------------

        channel_id = order.get("channel")

        if channel_id not in self.channels:
            errors.append(
                f"Invalid channel: {channel_id}"
            )

        # -------------------------------------------------
        # PRODUCT
        # -------------------------------------------------

        product_id = order.get("product_id")

        if product_id not in self.products:
            errors.append(
                f"Invalid product: {product_id}"
            )

        # -------------------------------------------------
        # VARIANT
        # -------------------------------------------------

        variant_id = order.get("variant_id")

        if variant_id not in self.variants:
            errors.append(
                f"Invalid variant: {variant_id}"
            )

        # -------------------------------------------------
        # PRODUCT → VARIANT RELATIONSHIP
        # -------------------------------------------------

        if (
            product_id in self.products
            and variant_id in self.variants
        ):
            variant = self.variants[variant_id]

            if variant.get("product_id") != product_id:
                errors.append(
                    f"Variant {variant_id} does not belong "
                    f"to product {product_id}"
                )

        # -------------------------------------------------
        # CATEGORY
        # -------------------------------------------------

        if product_id in self.products:

            product = self.products[product_id]

            if order.get("category") != product.get("category"):
                errors.append(
                    f"Category mismatch for product {product_id}"
                )

            if order.get("subcategory") != product.get("subcategory"):
                errors.append(
                    f"Subcategory mismatch for product {product_id}"
                )

        # -------------------------------------------------
        # QUANTITY
        # -------------------------------------------------

        quantity = order.get("quantity")

        if not isinstance(quantity, int):
            errors.append("Quantity must be an integer")

        elif quantity <= 0:
            errors.append("Quantity must be greater than zero")

        # -------------------------------------------------
        # PRICE
        # -------------------------------------------------

        unit_price = order.get("unit_price")

        if not isinstance(unit_price, (int, float)):
            errors.append("Unit price must be numeric")

        elif unit_price <= 0:
            errors.append("Unit price must be greater than zero")

        # -------------------------------------------------
        # GROSS AMOUNT
        # -------------------------------------------------

        gross_amount = order.get("gross_amount")

        if not isinstance(gross_amount, (int, float)):
            errors.append("Gross amount must be numeric")

        elif isinstance(quantity, int) and isinstance(
            unit_price, (int, float)
        ):

            expected_amount = round(
                quantity * unit_price,
                2
            )

            if gross_amount != expected_amount:
                errors.append(
                    f"Gross amount mismatch: "
                    f"expected {expected_amount}, "
                    f"got {gross_amount}"
                )

        # -------------------------------------------------
        # RESULT
        # -------------------------------------------------

        return {
            "valid": len(errors) == 0,
            "errors": errors
        }