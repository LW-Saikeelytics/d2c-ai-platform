import random

class OrderEngine:

    def __init__(self, config, simulation_state, customer_engine):
        self.config = config
        self.simulation_state = simulation_state
        self.customer_engine = customer_engine

        self.random = random.Random(42)

        self.order_counter = 0

        print("Order engine initialized successfully.")

    # ---------------------------------------------------------
    # ORDER ID
    # ---------------------------------------------------------

    def _generate_order_id(self):
        self.order_counter += 1
        return f"ORD-{self.order_counter:08d}"

    # ---------------------------------------------------------
    # PRODUCT SELECTION
    # ---------------------------------------------------------

    def _choose_product(
        self,
        customer
    ):

        products = self.config["products"]

        preferred_categories = customer.get(
            "preferred_categories",
            []
        )

        preferred_products = [
            product
            for product in products
            if product.get("category")
            in preferred_categories
        ]

        candidates = (
            preferred_products
            if preferred_products
            else products
        )

        weights = [
            self.customer_engine
            .get_product_selection_weight(
                customer,
                product
            )
            for product in candidates
        ]

        return self.random.choices(
            candidates,
            weights=weights,
            k=1
        )[0]
    # ---------------------------------------------------------
    # VARIANT SELECTION
    # ---------------------------------------------------------

    def _choose_variant(
        self,
        product,
        customer
    ):

        variants = self.config["variants"]

        matching_variants = [
            variant
            for variant in variants
            if variant.get("product_id")
            == product.get("product_id")
        ]

        if not matching_variants:
            raise ValueError(
                f"No variants found for product "
                f"{product.get('product_id')}"
            )

        if len(matching_variants) == 1:
            return matching_variants[0]

        sorted_variants = sorted(
            matching_variants,
            key=lambda variant:
                variant.get(
                    "unit_price",
                    0
                )
        )

        price_tendency = customer.get(
            "price_tendency",
            "medium"
        )

        count = len(
            sorted_variants
        )

        if price_tendency == "low":

            weights = [
                (count - index) ** 2
                for index in range(count)
            ]

        elif price_tendency == "high":

            weights = [
                (index + 1) ** 2
                for index in range(count)
            ]

        else:

            weights = [
                1
                for _ in sorted_variants
            ]

        return self.random.choices(
            sorted_variants,
            weights=weights,
            k=1
        )[0]

    # ---------------------------------------------------------
    # PRICE RESOLUTION
    # ---------------------------------------------------------

    def _resolve_price(self, product, variant):
        """
        Resolve the selling price from the existing master-data
        structure.

        We deliberately check both product and variant because
        the price ownership is defined by the master schema.
        """

        possible_price_fields = [
            "selling_price",
            "unit_price",
            "base_price",
            "mrp",
            "price"
        ]

        # First check variant
        for field in possible_price_fields:
            if field in variant:
                return float(variant[field])

        # Then check product
        for field in possible_price_fields:
            if field in product:
                return float(product[field])

        raise ValueError(
            f"No price field found for product "
            f"{product.get('product_id')} / "
            f"variant {variant.get('variant_id')}"
        )

    # ---------------------------------------------------------
    # QUANTITY
    # ---------------------------------------------------------

    def _choose_quantity(
        self,
        customer,
        product
    ):

        order_value_config = (
            self.config["company"].get(
                "order_value_behavior",
                {}
            )
        )

        category_weights = (
            order_value_config.get(
                "category_quantity_weights",
                {}
            )
        )

        category = product.get(
            "category"
        )

        quantity_config = (
            category_weights.get(
                category,
                {
                    "1": 95,
                    "2": 5
                }
            )
        )

        quantities = [
            int(quantity)
            for quantity
            in quantity_config.keys()
        ]

        weights = [
            float(weight)
            for weight
            in quantity_config.values()
        ]

        # --------------------------------------------------
        # Adjust multi-unit likelihood by product price band
        # --------------------------------------------------

        price_band = product.get(
            "price_band",
            "Mid"
        )

        multi_unit_multipliers = (
            order_value_config.get(
                "multi_unit_price_band_multipliers",
                {}
            )
        )

        multi_unit_multiplier = (
            multi_unit_multipliers.get(
                price_band,
                1.00
            )
        )

        adjusted_weights = []

        for quantity, weight in zip(
            quantities,
            weights
        ):

            if quantity > 1:

                weight *= (
                    multi_unit_multiplier
                )

            adjusted_weights.append(
                weight
            )

        return self.random.choices(
            quantities,
            weights=adjusted_weights,
            k=1
        )[0]

    # ---------------------------------------------------------
    # ORDER CREATION
    # ---------------------------------------------------------

    def generate_order(self, customer, simulation_day=1):

        product = self._choose_product(customer)

        variant = self._choose_variant(product,customer)

        quantity = self._choose_quantity(customer,product)

        unit_price = self._resolve_price(
            product,
            variant
        )

        order_id = self._generate_order_id()

        order = {
            "order_id": order_id,

            "simulation_day": simulation_day,

            "customer_id": customer["customer_id"],

            "segment": customer["segment"],

            "city_id": customer["city_id"],

            "region": customer["region"],

            "channel": customer["acquisition_channel"],

            "product_id": product["product_id"],

            "variant_id": variant["variant_id"],

            "category": product.get("category"),

            "subcategory": product.get("subcategory"),

            "quantity": quantity,

            "unit_price": unit_price,

            "gross_amount": round(
                unit_price * quantity,
                2
            )
        }

        return order

if __name__ == "__main__":

    from collections import Counter

    from simulation.config_loader import (
        load_all_config
    )

    from simulation.state import (
        SimulationState
    )

    from simulation.customer_engine import (
        CustomerEngine
    )

    config = load_all_config()
    state = SimulationState()

    customer_engine = CustomerEngine(
        config=config,
        state=state,
        seed=42
    )

    order_engine = OrderEngine(
        config=config,
        simulation_state=state,
        customer_engine=customer_engine
    )

    print("\n" + "=" * 60)
    print("PRICE SENSITIVITY CHECK")
    print("=" * 60)

    test_customers = {
        "low": {
            "price_tendency": "low",
            "preferred_categories": []
        },

        "medium": {
            "price_tendency": "medium",
            "preferred_categories": []
        },

        "high": {
            "price_tendency": "high",
            "preferred_categories": []
        }
    }

    for tendency, customer in (
        test_customers.items()
    ):

        counts = Counter()

        for _ in range(1000):

            product = (
                order_engine._choose_product(
                    customer
                )
            )

            counts[
                product["price_band"]
            ] += 1

        print(
            f"{tendency}: "
            f"{dict(counts)}"
        )


    # --------------------------------------------------
    # VARIANT PRICE CHECK
    # --------------------------------------------------

    mattress = next(
        product
        for product in config["products"]
        if product["product_id"]
        == "PRD-MAT-001"
    )

    averages = {}

    for tendency in [
        "low",
        "high"
    ]:

        customer = {
            "price_tendency":
                tendency
        }

        prices = []

        for _ in range(1000):

            variant = (
                order_engine._choose_variant(
                    mattress,
                    customer
                )
            )

            prices.append(
                variant["unit_price"]
            )

        averages[tendency] = (
            sum(prices)
            / len(prices)
        )

        print(
            f"{tendency} variant "
            f"average price: "
            f"{averages[tendency]:.2f}"
        )

    assert (
        averages["low"]
        <
        averages["high"]
    )

    print(
        "\nPRICE SENSITIVITY CHECK PASSED."
    )

    print("\n" + "=" * 60)
    print("PRODUCT POPULARITY CHECK")
    print("=" * 60)

    from collections import Counter

    test_customer = {
        "price_tendency": "medium",
        "preferred_categories": [
            "Pillows"
        ]
    }

    counts = Counter()

    for _ in range(5000):

        product = (
            order_engine._choose_product(
                test_customer
            )
        )

        counts[
            product["product_id"]
        ] += 1


    for product_id, count in (
        counts.most_common()
    ):

        print(
            f"{product_id}: {count}"
        )


    # Same price band:
    # both PIL-001 and PIL-002 are Mid.
    #
    # Therefore the popularity multiplier
    # should make PIL-001 clearly stronger.

    assert (
        counts["PRD-PIL-001"]
        >
        counts["PRD-PIL-002"]
    )

    print(
        "\nPRODUCT POPULARITY CHECK PASSED."
    )

    print(
        "\nINVENTORY CONFIG:",
        config["company"].get(
            "inventory_behavior"
        )
    )

    print(
        "\nORDER VALUE CONFIG:",
        config["company"].get(
            "order_value_behavior"
        )
    )

    print("\n" + "=" * 60)
    print("INVENTORY EFFECT CHECK")
    print("=" * 60)

    north_customer = {
        "region": "North",
        "price_tendency": "medium",
        "preferred_categories": [
            "Beds"
        ]
    }

    test_product_ids = [
        "PRD-BED-001",
        "PRD-BED-004"
    ]

    for product_id in test_product_ids:

        product = next(
            product
            for product in config["products"]
            if product["product_id"]
            == product_id
        )

        status = (
            customer_engine
            .get_product_inventory_status(
                north_customer,
                product
            )
        )

        inventory_weight = (
            customer_engine
            .get_product_inventory_weight(
                north_customer,
                product
            )
        )

        print(
            f"{product_id}: "
            f"{status} | "
            f"weight={inventory_weight}"
        )


    # --------------------------------------------------
    # Prove an out-of-stock product cannot be selected.
    # --------------------------------------------------

    counts = Counter()

    for _ in range(5000):

        product = (
            order_engine._choose_product(
                north_customer
            )
        )

        counts[
            product["product_id"]
        ] += 1


    print(
        f"PRD-BED-004 selections: "
        f"{counts['PRD-BED-004']}"
    )

    assert (
        counts["PRD-BED-004"]
        == 0
    )

    print(
        "\nINVENTORY EFFECT CHECK PASSED."
    )

    print(
        "\nORDER VALUE CONFIG:",
        config["company"].get(
            "order_value_behavior"
        )
    )

    print("\n" + "=" * 60)
    print("ORDER VALUE DISTRIBUTION CHECK")
    print("=" * 60)

    test_customer = {
        "price_tendency": "medium"
    }

    mattress = next(
        product
        for product in config["products"]
        if product["product_id"]
        == "PRD-MAT-001"
    )

    pillow = next(
        product
        for product in config["products"]
        if product["product_id"]
        == "PRD-PIL-001"
    )

    mattress_quantities = Counter()
    pillow_quantities = Counter()


    for _ in range(5000):

        mattress_quantity = (
            order_engine._choose_quantity(
                test_customer,
                mattress
            )
        )

        pillow_quantity = (
            order_engine._choose_quantity(
                test_customer,
                pillow
            )
        )

        mattress_quantities[
            mattress_quantity
        ] += 1

        pillow_quantities[
            pillow_quantity
        ] += 1


    print(
        "Mattress quantities:",
        dict(mattress_quantities)
    )

    print(
        "Pillow quantities:",
        dict(pillow_quantities)
    )


    mattress_multi_unit = (
        sum(
            count
            for quantity, count
            in mattress_quantities.items()
            if quantity > 1
        )
        / 5000
    )

    pillow_multi_unit = (
        sum(
            count
            for quantity, count
            in pillow_quantities.items()
            if quantity > 1
        )
        / 5000
    )


    print(
        f"Mattress multi-unit share: "
        f"{mattress_multi_unit:.4f}"
    )

    print(
        f"Pillow multi-unit share: "
        f"{pillow_multi_unit:.4f}"
    )


    assert (
        pillow_multi_unit
        >
        mattress_multi_unit
    )

    print("\n" + "=" * 60)
    sample_customers = (
        customer_engine
        .generate_customer_population(
            count=100,
            start_id=1000,
            current_day=1
        )
    )

    gross_amounts = []


    for _ in range(5000):

        customer = (
            order_engine.random.choice(
                sample_customers
            )
        )

        order = (
            order_engine.generate_order(
                customer=customer,
                simulation_day=1
            )
        )

        gross_amounts.append(
            order["gross_amount"]
        )


    gross_amounts.sort()

    count = len(
        gross_amounts
    )

    median = (
        gross_amounts[
            count // 2
        ]
    )

    p90 = (
        gross_amounts[
            int(
                count * 0.90
            )
        ]
    )

    average = (
        sum(gross_amounts)
        / count
    )

    unique_values = len(
        set(gross_amounts)
    )


    print(
        f"Minimum order value: "
        f"{gross_amounts[0]:.2f}"
    )

    print(
        f"Median order value: "
        f"{median:.2f}"
    )

    print(
        f"Average order value: "
        f"{average:.2f}"
    )

    print(
        f"P90 order value: "
        f"{p90:.2f}"
    )

    print(
        f"Maximum order value: "
        f"{gross_amounts[-1]:.2f}"
    )

    print(
        f"Unique order values: "
        f"{unique_values}"
    )


    assert (
        gross_amounts[0]
        <
        median
        <
        p90
        <=
        gross_amounts[-1]
    )

    assert (
        unique_values
        >= 10
    )

    print(
        "\nORDER VALUE DISTRIBUTION CHECK PASSED."
    )