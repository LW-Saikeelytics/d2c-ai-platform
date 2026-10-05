import random

class ConversionEngine:

    def __init__(self, config, state, seed=42):
        """
        Determine whether a customer progresses from
        behavioural activity toward a purchase.

        IMPORTANT:
        This engine does NOT create orders.

        It only produces a conversion decision.
        """

        self.config = config
        self.state = state

        # Dedicated random generator for reproducibility.
        self.random = random.Random(seed)

    def calculate_conversion_probability(
        self,
        customer,
        events
    ):

        event_types = {
            event["event_type"]
            for event in events
        }

        # No meaningful behavioural activity.
        if "product_view" not in event_types:
            return 0.0

        conversion_config = (
            self.config["company"].get(
                "conversion_distribution",
                {}
            )
        )

        base_probabilities = (
            conversion_config.get(
                "base_probabilities",
                {}
            )
        )

        # --------------------------------------------------
        # 1. Funnel stage
        # --------------------------------------------------

        if "purchase_intent" in event_types:

            probability = (
                base_probabilities.get(
                    "purchase_intent",
                    0.38
                )
            )

        elif "add_to_cart" in event_types:

            probability = (
                base_probabilities.get(
                    "add_to_cart",
                    0.16
                )
            )

        else:

            probability = (
                base_probabilities.get(
                    "view_only",
                    0.04
                )
            )

        # --------------------------------------------------
        # 2. Repeat-purchase tendency
        # --------------------------------------------------

        repeat_tendency = customer.get(
            "repeat_purchase_tendency",
            "medium"
        )

        repeat_multipliers = (
            conversion_config.get(
                "repeat_tendency_multipliers",
                {}
            )
        )

        probability *= (
            repeat_multipliers.get(
                repeat_tendency,
                1.00
            )
        )

        # --------------------------------------------------
        # 3. Purchase propensity
        # --------------------------------------------------

        purchase_propensity = customer.get(
            "purchase_propensity",
            0.18
        )

        propensity_reference = (
            conversion_config.get(
                "propensity_reference",
                0.18
            )
        )

        min_propensity_multiplier = (
            conversion_config.get(
                "propensity_min_multiplier",
                0.65
            )
        )

        max_propensity_multiplier = (
            conversion_config.get(
                "propensity_max_multiplier",
                1.35
            )
        )

        if propensity_reference > 0:

            propensity_multiplier = (
                purchase_propensity
                / propensity_reference
            )

        else:

            propensity_multiplier = 1.00

        propensity_multiplier = max(
            min_propensity_multiplier,
            min(
                propensity_multiplier,
                max_propensity_multiplier
            )
        )

        probability *= (
            propensity_multiplier
        )

        # --------------------------------------------------
        # 4. Behavioral personality
        # --------------------------------------------------

        profile_name = customer.get(
            "behavior_profile",
            "balanced"
        )

        behavior_profiles = (
            self.config["company"].get(
                "behavior_profiles",
                {}
            )
        )

        profile_config = (
            behavior_profiles.get(
                profile_name,
                {}
            )
        )

        probability *= (
            profile_config.get(
                "conversion_multiplier",
                1.00
            )
        )

        # --------------------------------------------------
        # 5. Preferred-category relevance
        # --------------------------------------------------

        product_categories = {
            event.get("category")
            for event in events
            if event.get("category")
        }

        preferred_categories = set(
            customer.get(
                "preferred_categories",
                []
            )
        )

        if (
            product_categories
            & preferred_categories
        ):

            probability *= (
                conversion_config.get(
                    "preferred_category_multiplier",
                    1.08
                )
            )

        # --------------------------------------------------
        # 6. Purchase history
        # --------------------------------------------------

        history_multipliers = (
            conversion_config.get(
                "purchase_history_multipliers",
                {}
            )
        )

        if customer.get(
            "lifetime_orders",
            0
        ) > 0:

            probability *= (
                history_multipliers.get(
                    "repeat_customer",
                    1.05
                )
            )

        else:

            probability *= (
                history_multipliers.get(
                    "first_purchase",
                    0.95
                )
            )

        # --------------------------------------------------
        # Final bounds
        # --------------------------------------------------

        maximum_probability = (
            conversion_config.get(
                "maximum_probability",
                0.75
            )
        )

        probability = max(
            0.0,
            min(
                probability,
                maximum_probability
            )
        )

        return round(
            probability,
            4
        )

    def should_convert(
        self,
        customer,
        events
    ):
        event_types = {
            event.get("event_type")
            for event in events
        }

        # --------------------------------------------------
        # Funnel eligibility
        # --------------------------------------------------
        #
        # Final purchase conversion is only possible after
        # explicit purchase intent.
        #
        # View-only customers and abandoned carts cannot
        # directly become purchases.
        # --------------------------------------------------

        if "purchase_intent" not in event_types:

            return {
                "converted": False,
                "conversion_probability": 0.0,
                "product_id": None
            }
        
        """
        Determine whether the customer converts.

        Returns:

        {
            "converted": True/False,
            "conversion_probability": 0.xx,
            "product_id": "..."/None
        }
        """
        probability = self.calculate_conversion_probability(
            customer=customer,
            events=events
        )

        product = self.get_conversion_product(events)

        # No product means no possible conversion.
        if product is None:
            return {
                "converted": False,
                "conversion_probability": probability,
                "product_id": None
            }

        converted = (
            self.random.random()
            < probability
        )

        return {
            "converted": converted,
            "conversion_probability": probability,
            "product_id": (
                product["product_id"]
                if converted
                else None
            )
        }

    def get_conversion_product(
        self,
        events
    ):
        """
        Determine which product the customer is
        showing purchase intent toward.

        Priority:

        1. purchase_intent
        2. add_to_cart
        3. product_view
        """

        priority = [
            "purchase_intent",
            "add_to_cart",
            "product_view"
        ]

        for event_type in priority:

            for event in reversed(events):

                if event.get("event_type") == event_type:

                    product_id = event.get(
                        "product_id"
                    )

                    if product_id is None:
                        continue

                    # Find the corresponding product
                    # in master data.
                    for product in self.config["products"]:

                        if product["product_id"] == product_id:
                            return product

        return None


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    from simulation.config_loader import load_all_config
    from simulation.state import SimulationState
    from simulation.customer_engine import CustomerEngine
    from simulation.event_engine import EventEngine
    from simulation.behavior_engine import BehaviorEngine

    config = load_all_config()
    state = SimulationState()

    customer_engine = CustomerEngine(
        config=config,
        state=state,
        seed=42
    )

    event_engine = EventEngine(
        config=config,
        state=state,
        seed=42
    )

    behavior_engine = BehaviorEngine(
        config=config,
        state=state,
        customer_engine=customer_engine,
        event_engine=event_engine,
        seed=42
    )

    conversion_engine = ConversionEngine(
        config=config,
        state=state,
        seed=42
    )

    # --------------------------------------------------------
    # Generate test customer population
    # --------------------------------------------------------

    customers = customer_engine.generate_customer_population(
        count=10,
        start_id=1,
        current_day=1
    )

    print("=" * 60)
    print("CONVERSION ENGINE TEST")
    print("=" * 60)

    print("\nSimulating behaviour for all customers...")

    total_converted = 0
    total_evaluated = 0

    # --------------------------------------------------------
    # Simulate behaviour for each customer
    # --------------------------------------------------------

    for customer in customers:

        events = behavior_engine.simulate_customer_day(
            customer=customer,
            simulation_day=1
        )

        # Only evaluate customers who generated events.
        if not events:
            continue

        total_evaluated += 1

        result = conversion_engine.should_convert(
            customer=customer,
            events=events
        )

        print(
            f"\n{customer['customer_id']}"
        )

        print(
            f"Events generated: {len(events)}"
        )

        print(
            "Event types:",
            [
                event["event_type"]
                for event in events
            ]
        )

        print(
            "Conversion probability:",
            result["conversion_probability"]
        )

        print(
            "Conversion decision:",
            result["converted"]
        )

        print(
            "Conversion product:",
            result["product_id"]
        )

        if result["converted"]:
            total_converted += 1

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print("\n" + "=" * 60)
    print("CONVERSION SUMMARY")
    print("=" * 60)

    print(
        "Customers evaluated:",
        total_evaluated
    )

    print(
        "Customers converted:",
        total_converted
    )

    if total_evaluated > 0:

        conversion_rate = (
            total_converted
            / total_evaluated
        )

        print(
            "Conversion rate:",
            f"{conversion_rate:.2%}"
        )

    else:

        print(
            "Conversion rate:",
            "0.00%"
        )

    print(
        "\nTotal events stored in state:",
        len(state.events)
    )

    print("\n" + "=" * 60)
    print("CONVERSION DISTRIBUTION CHECK")
    print("=" * 60)

    test_customer = {
        "repeat_purchase_tendency": "medium",
        "purchase_propensity": 0.18,
        "behavior_profile": "balanced",
        "preferred_categories": [
            "Mattresses"
        ],
        "lifetime_orders": 0
    }

    view_events = [
        {
            "event_type": "product_view",
            "product_id": "PRD-MAT-001",
            "category": "Mattresses"
        }
    ]

    cart_events = [
        {
            "event_type": "product_view",
            "product_id": "PRD-MAT-001",
            "category": "Mattresses"
        },
        {
            "event_type": "add_to_cart",
            "product_id": "PRD-MAT-001",
            "category": "Mattresses"
        }
    ]

    intent_events = [
        {
            "event_type": "product_view",
            "product_id": "PRD-MAT-001",
            "category": "Mattresses"
        },
        {
            "event_type": "add_to_cart",
            "product_id": "PRD-MAT-001",
            "category": "Mattresses"
        },
        {
            "event_type": "purchase_intent",
            "product_id": "PRD-MAT-001",
            "category": "Mattresses"
        }
    ]


    view_probability = (
        conversion_engine
        .calculate_conversion_probability(
            test_customer,
            view_events
        )
    )

    cart_probability = (
        conversion_engine
        .calculate_conversion_probability(
            test_customer,
            cart_events
        )
    )

    intent_probability = (
        conversion_engine
        .calculate_conversion_probability(
            test_customer,
            intent_events
        )
    )


    print(
        f"View only: {view_probability}"
    )

    print(
        f"Add to cart: {cart_probability}"
    )

    print(
        f"Purchase intent: {intent_probability}"
    )


    assert (
        view_probability
        <
        cart_probability
        <
        intent_probability
    )

    same_cart_events = cart_events

    customers = {
        "low_intent": {
            "repeat_purchase_tendency": "low",
            "purchase_propensity": 0.08,
            "behavior_profile": "cautious",
            "preferred_categories": [],
            "lifetime_orders": 0
        },

        "medium_intent": {
            "repeat_purchase_tendency": "medium",
            "purchase_propensity": 0.18,
            "behavior_profile": "balanced",
            "preferred_categories": [],
            "lifetime_orders": 0
        },

        "high_intent": {
            "repeat_purchase_tendency": "high",
            "purchase_propensity": 0.30,
            "behavior_profile": "engaged",
            "preferred_categories": [
                "Mattresses"
            ],
            "lifetime_orders": 3
        }
    }


    customer_probabilities = {}

    for label, customer in customers.items():

        probability = (
            conversion_engine
            .calculate_conversion_probability(
                customer,
                same_cart_events
            )
        )

        customer_probabilities[
            label
        ] = probability

        print(
            f"{label}: "
            f"{probability}"
        )


    assert (
        customer_probabilities["low_intent"]
        <
        customer_probabilities["medium_intent"]
        <
        customer_probabilities["high_intent"]
    )

    print(
        "\nCONVERSION DISTRIBUTION CHECK PASSED."
    )