import random
from datetime import date, timedelta

class BehaviorEngine:

    def __init__(
        self,
        config,
        state,
        customer_engine,
        event_engine,
        seed=42
    ):
        self.config = config
        self.state = state
        self.customer_engine = customer_engine
        self.event_engine = event_engine

        self.random = random.Random(seed)

    def simulate_customer_day(
        self,
        customer,
        simulation_day
    ):
        """
        Simulate one customer's behavioural activity
        for one simulation day.

        This generates behavioural events only.
        It does not create orders.
        """

        events = []

        # --------------------------------------------------
        # Update lifecycle / inactivity status
        # --------------------------------------------------

        customer["status"] = (
            self.customer_engine
            .get_customer_activity_status(
                customer,
                simulation_day
            )
        )

        # --------------------------------------------------
        # STEP 1: Decide whether the customer is active today
        # --------------------------------------------------

        activity_probability = self._calculate_activity_probability(
            customer,
            simulation_day
        )

        if self.random.random() > activity_probability:
            return events

        # --------------------------------------------------
        # STEP 2: Choose a preferred category
        # --------------------------------------------------

        category = self._choose_category(customer)

        if category is None:
            return events

        # --------------------------------------------------
        # STEP 3: Choose a product from that category
        # --------------------------------------------------

        product = self._choose_product(
            customer,
            category)

        if product is None:
            return events

        # --------------------------------------------------
        # STEP 4: Product view
        # --------------------------------------------------

        view_event = self.event_engine.generate_product_view(
            customer=customer,
            product=product,
            simulation_day=simulation_day
        )

        events.append(view_event)

        # --------------------------------------------------
        # STEP 5: Decide whether customer adds to cart
        # --------------------------------------------------

        add_to_cart_probability = (
            self._calculate_add_to_cart_probability(
                customer
            )
        )

        if self.random.random() > add_to_cart_probability:
            return events

        # --------------------------------------------------
        # STEP 6: Add to cart
        # --------------------------------------------------

        cart_event = self.event_engine.generate_add_to_cart(
            customer=customer,
            product=product,
            simulation_day=simulation_day
        )

        events.append(cart_event)

        # --------------------------------------------------
        # STEP 7: Decide purchase intent vs abandonment
        # --------------------------------------------------

        purchase_probability = (
            self._calculate_purchase_probability(
                customer,
                simulation_day,
                product
            )
        )

        if self.random.random() <= purchase_probability:

            purchase_event = self.event_engine.generate_purchase_intent(
                customer_id=customer["customer_id"],
                product=product,
                simulation_day=simulation_day
            )

            events.append(purchase_event)

        else:

            abandonment_event = (
                self.event_engine.generate_cart_abandonment(
                    customer=customer,
                    product=product,
                    simulation_day=simulation_day
                )
            )

            events.append(abandonment_event)

        return events

    # ======================================================
    # ACTIVITY
    # ======================================================

    def _calculate_activity_probability(
        self,
        customer,
        simulation_day
    ):

        propensity = customer.get(
            "purchase_propensity",
            0.10
        )

        repeat_tendency = customer.get(
            "repeat_purchase_tendency",
            "medium"
        )

        repeat_multiplier_map = {
            "high": 1.50,
            "medium": 1.00,
            "low": 0.70
        }

        seasonality_multiplier = (
            self._get_seasonality_multiplier(
                simulation_day
            )
        )

        lifecycle_multiplier = (
            self.customer_engine
            .get_lifecycle_activity_multiplier(
                customer,
                simulation_day
            )
        )

        repeat_multiplier = (
            repeat_multiplier_map.get(
                repeat_tendency,
                1.00
            )
        )

        churn_multiplier = (
            self.customer_engine
            .get_churn_activity_multiplier(
                customer,
                simulation_day
            )
        )

        behavior_multiplier = (
            self.customer_engine
            .get_behavior_profile_multiplier(
                customer,
                "activity_multiplier"
            )
        )

        # --------------------------------------------------
        # WEEKDAY / WEEKEND REALISM
        # --------------------------------------------------

        day_name = self._get_day_name(
            simulation_day
        )

        company_config = self.config[
            "company"
        ]

        weekday_multipliers = (
            company_config.get(
                "weekday_activity_multipliers",
                {}
            )
        )

        time_multiplier = (
            weekday_multipliers.get(
                day_name,
                1.00
            )
        )

        probability = (
            propensity
            * repeat_multiplier
            * time_multiplier
            * seasonality_multiplier
            * lifecycle_multiplier
            * churn_multiplier
            * behavior_multiplier
        )

        return min(
            round(probability, 4),
            0.80
        )

    def _get_day_name(
        self,
        simulation_day
    ):

        simulation_date = (
            self._get_simulation_date(
                simulation_day
            )
        )

        if simulation_date is not None:

            return simulation_date.strftime(
                "%A"
            )

        # Fallback for older configurations
        weekdays = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday"
        ]

        start_weekday = (
            self.config["company"].get(
                "simulation_start_weekday",
                "Monday"
            )
        )

        try:
            start_index = weekdays.index(
                start_weekday
            )

        except ValueError:
            start_index = 0

        day_index = (
            start_index
            + simulation_day
            - 1
        ) % 7

        return weekdays[day_index]

    def _get_simulation_date(
        self,
        simulation_day
    ):

        start_date_text = (
            self.config["company"].get(
                "simulation_start_date"
            )
        )

        if not start_date_text:
            return None

        try:
            start_date = date.fromisoformat(
                start_date_text
            )

        except ValueError:
            return None

        return (
            start_date
            + timedelta(
                days=simulation_day - 1
            )
        )

    def _get_seasonality_multiplier(
        self,
        simulation_day
    ):

        simulation_date = (
            self._get_simulation_date(
                simulation_day
            )
        )

        if simulation_date is None:
            return 1.00

        month_name = (
            simulation_date.strftime(
                "%B"
            )
        )

        multipliers = (
            self.config["company"].get(
                "seasonality_month_multipliers",
                {}
            )
        )

        return multipliers.get(
            month_name,
            1.00
        )
    
    # ======================================================
    # CATEGORY SELECTION
    # ======================================================

    def _choose_category(self, customer):

        preferred_categories = customer.get(
            "preferred_categories",
            []
        )

        if preferred_categories:

            return self.random.choice(
                preferred_categories
            )

        categories = sorted(
            set(
                product["category"]
                for product in self.config["products"]
            )
        )

        if not categories:
            return None

        return self.random.choice(categories)

    # ======================================================
    # PRODUCT SELECTION
    # ======================================================

    def _choose_product(
        self,
        customer,
        category
    ):

        products = [
            product
            for product in self.config["products"]
            if product["category"] == category
        ]

        if not products:
            return None

        weights = [
            self.customer_engine
            .get_product_selection_weight(
                customer,
                product
            )
            for product in products
        ]

        return self.random.choices(
            products,
            weights=weights,
            k=1
        )[0]
    # ======================================================
    # ADD TO CART
    # ======================================================

    def _calculate_add_to_cart_probability(
        self,
        customer
    ):

        funnel_config = (
            self.config["company"].get(
                "event_funnel_behavior",
                {}
            )
        )

        probability = (
            funnel_config.get(
                "base_add_to_cart_probability",
                0.35
            )
        )

        discount_sensitivity = customer.get(
            "discount_sensitivity",
            "medium"
        )

        if discount_sensitivity == "high":
            probability += 0.10

        elif discount_sensitivity == "low":
            probability -= 0.05

        behavior_multiplier = (
            self.customer_engine
            .get_behavior_profile_multiplier(
                customer,
                "cart_multiplier"
            )
        )

        probability *= behavior_multiplier

        minimum_probability = (
            funnel_config.get(
                "minimum_stage_probability",
                0.05
            )
        )

        maximum_probability = (
            funnel_config.get(
                "maximum_stage_probability",
                0.90
            )
        )

        return max(
            minimum_probability,
            min(
                probability,
                maximum_probability
            )
        )

    # ======================================================
    # PURCHASE
    # ======================================================

    def _get_repeat_purchase_multiplier(
        self,
        customer,
        simulation_day
    ):

        lifetime_orders = customer.get(
            "lifetime_orders",
            0
        )

        last_order_day = customer.get(
            "last_order_day"
        )

        # No previous purchase:
        # this is not a repeat-purchase case.
        if (
            lifetime_orders == 0
            or last_order_day is None
        ):
            return 1.00

        days_since_purchase = max(
            simulation_day
            - last_order_day,
            0
        )

        config = (
            self.config["company"].get(
                "repeat_purchase_behavior",
                {}
            )
        )

        if days_since_purchase <= 3:

            return config.get(
                "0_to_3_days_multiplier",
                0.35
            )

        if days_since_purchase <= 7:

            return config.get(
                "4_to_7_days_multiplier",
                0.55
            )

        if days_since_purchase <= 14:

            return config.get(
                "8_to_14_days_multiplier",
                0.80
            )

        if days_since_purchase <= 30:

            return config.get(
                "15_to_30_days_multiplier",
                1.00
            )

        return config.get(
            "31_plus_days_multiplier",
            1.10
        )

    def _calculate_purchase_probability(
        self,
        customer,
        simulation_day,
        product=None
    ):

        funnel_config = (
            self.config["company"].get(
                "event_funnel_behavior",
                {}
            )
        )

        probability = (
            funnel_config.get(
                "base_purchase_intent_probability",
                0.25
            )
        )

        repeat_tendency = customer.get(
            "repeat_purchase_tendency",
            "medium"
        )

        if repeat_tendency == "high":
            probability += 0.15

        elif repeat_tendency == "low":
            probability -= 0.10

        discount_sensitivity = customer.get(
            "discount_sensitivity",
            "medium"
        )

        if discount_sensitivity == "high":
            probability -= 0.05

        repeat_purchase_multiplier = (
            self._get_repeat_purchase_multiplier(
                customer,
                simulation_day
            )
        )

        probability *= (
            repeat_purchase_multiplier
        )

        behavior_multiplier = (
            self.customer_engine
            .get_behavior_profile_multiplier(
                customer,
                "purchase_multiplier"
            )
        )

        probability *= behavior_multiplier

        promotion_multiplier = (
            self._get_promotion_multiplier(
                customer,
                simulation_day,
                product
            )
        )

        probability *= (
            promotion_multiplier
        )

        minimum_probability = (
            funnel_config.get(
                "minimum_stage_probability",
                0.05
            )
        )

        maximum_probability = (
            funnel_config.get(
                "maximum_stage_probability",
                0.90
            )
        )

        return max(
            minimum_probability,
            min(
                probability,
                maximum_probability
            )
        )

    def _is_promotion_eligible(
        self,
        promotion,
        customer,
        simulation_day,
        product=None
    ):

        start_day = promotion.get(
            "start_day",
            1
        )

        end_day = promotion.get(
            "end_day",
            simulation_day
        )

        if not (
            start_day
            <= simulation_day
            <= end_day
        ):
            return False

        eligibility = promotion.get(
            "eligibility"
        )

        # ----------------------------------------------
        # NEW CUSTOMER OFFER
        # ----------------------------------------------

        if eligibility == "new_customer":

            return (
                customer.get(
                    "lifetime_orders",
                    0
                )
                == 0
            )

        # ----------------------------------------------
        # MOBILE APP NEW CUSTOMER
        # ----------------------------------------------

        if (
            eligibility
            == "mobile_app_new_customer"
        ):

            return (
                customer.get(
                    "lifetime_orders",
                    0
                )
                == 0
                and
                customer.get(
                    "acquisition_channel"
                )
                == "CH-APP"
            )

        # ----------------------------------------------
        # CATEGORY PROMOTION
        # ----------------------------------------------

        if (
            eligibility
            == "selected_categories"
        ):

            if product is None:
                return False

            target_categories = (
                promotion.get(
                    "target_categories",
                    []
                )
            )

            return (
                product.get("category")
                in target_categories
            )

        # ----------------------------------------------
        # BUNDLE PROMOTIONS
        # Not supported by current one-product order model.
        # ----------------------------------------------

        if (
            eligibility
            == "selected_product_combinations"
        ):
            return False

        return False

    def _get_promotion_multiplier(
        self,
        customer,
        simulation_day,
        product=None
    ):

        promotions = self.config.get(
            "promotions",
            []
        )

        band_multipliers = (
            self.config["company"]
            .get(
                "promotion_behavior",
                {}
            )
            .get(
                "discount_band_multipliers",
                {}
            )
        )

        applicable_multipliers = [
            1.00
        ]

        for promotion in promotions:

            if not self._is_promotion_eligible(
                promotion,
                customer,
                simulation_day,
                product
            ):
                continue

            discount_band = (
                promotion.get(
                    "discount_band"
                )
            )

            multiplier = (
                band_multipliers.get(
                    discount_band,
                    1.00
                )
            )

            applicable_multipliers.append(
                multiplier
            )

        # Use strongest applicable promotion rather
        # than stacking multiple offers.
        return max(
            applicable_multipliers
        )

if __name__ == "__main__":

    from simulation.config_loader import load_all_config
    from simulation.state import SimulationState
    from simulation.customer_engine import CustomerEngine
    from simulation.event_engine import EventEngine

    print("=" * 60)
    print("BEHAVIOR ENGINE TEST")
    print("=" * 60)

    config = load_all_config()
    state = SimulationState()

    state.counters["event"] = 0

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

    customers = customer_engine.generate_customer_population(
        count=10,
        start_id=1,
        current_day=1
    )

    print("\nSimulating behaviour for all customers...")

    total_events = 0

    for customer in customers:

        events = behavior_engine.simulate_customer_day(
            customer=customer,
            simulation_day=1
        )

        if events:
            print(
                f"\n{customer['customer_id']} "
                f"generated {len(events)} events:"
            )

            for event in events:
                print(event)

            total_events += len(events)

    print("\n" + "=" * 60)
    print("BEHAVIOR SUMMARY")
    print("=" * 60)

    print(f"Customers simulated: {len(customers)}")
    print(f"Total events generated: {total_events}")
    print(f"Events stored in state: {len(state.events)}")

    print("\nWEEKDAY MAPPING")

    for day in range(1, 15):

        day_name = (
            behavior_engine._get_day_name(day)
        )

        multiplier = (
            config["company"][
                "weekday_activity_multipliers"
            ][day_name]
        )

        print(
            f"Day {day}: "
            f"{day_name} "
            f"| multiplier={multiplier}"
        )

    print("\nCALENDAR / SEASONALITY MAPPING")

    test_days = [
        1,
        3,
        4,
        34,
        35,
        64,
        65,
        90
    ]

    for day in test_days:

        simulation_date = (
            behavior_engine._get_simulation_date(
                day
            )
        )

        day_name = (
            behavior_engine._get_day_name(
                day
            )
        )

        seasonality = (
            behavior_engine
            ._get_seasonality_multiplier(
                day
            )
        )

        print(
            f"Day {day}: "
            f"{simulation_date} | "
            f"{day_name} | "
            f"seasonality={seasonality}"
        )

    print("\n" + "=" * 60)
    print("TIME REALISM PROBABILITY CHECK")
    print("=" * 60)

    test_customer = customers[0]

    test_days = {
        "September Wednesday": 3,   # 2026-09-30
        "October Wednesday": 10,    # 2026-10-07

        "October Monday": 8,        # 2026-10-05
        "October Saturday": 13      # 2026-10-10
    }

    probabilities = {}

    for label, day in test_days.items():

        probability = (
            behavior_engine
            ._calculate_activity_probability(
                test_customer,
                day
            )
        )

        probabilities[label] = probability

        print(
            f"{label}: "
            f"day={day} | "
            f"probability={probability}"
        )


    # ----------------------------------------------------------
    # Seasonality check:
    # Same weekday, October should be stronger than September.
    # ----------------------------------------------------------

    assert (
        probabilities["October Wednesday"]
        >
        probabilities["September Wednesday"]
    )


    # ----------------------------------------------------------
    # Weekday/weekend check:
    # Same month, Saturday should be stronger than Monday.
    # ----------------------------------------------------------

    assert (
        probabilities["October Saturday"]
        >
        probabilities["October Monday"]
    )

    print(
        "\nTIME REALISM PROBABILITY CHECK PASSED."
    )

    print("\n" + "=" * 60)
    print("REPEAT PURCHASE BEHAVIOR CHECK")
    print("=" * 60)

    simulation_day = 50

    test_cases = [
        ("Never purchased", 0, None),
        ("Purchased yesterday", 2, 49),
        ("Purchased 5 days ago", 2, 45),
        ("Purchased 10 days ago", 2, 40),
        ("Purchased 20 days ago", 2, 30),
        ("Purchased 40 days ago", 2, 10)
    ]

    for label, lifetime_orders, last_order_day in test_cases:

        test_customer = {
            "lifetime_orders":
                lifetime_orders,

            "last_order_day":
                last_order_day
        }

        multiplier = (
            behavior_engine
            ._get_repeat_purchase_multiplier(
                test_customer,
                simulation_day
            )
        )

        print(
            f"{label}: "
            f"multiplier={multiplier}"
        )

    print("\n" + "=" * 60)
    print("BEHAVIORAL DIVERSITY CHECK")
    print("=" * 60)

    simulation_day = 10

    base_customer = {
        "purchase_propensity": 0.18,
        "repeat_purchase_tendency": "medium",
        "discount_sensitivity": "medium",
        "lifetime_orders": 0,
        "last_order_day": None,
        "registration_day": 1
    }

    results = {}

    for profile in [
        "cautious",
        "balanced",
        "engaged"
    ]:

        test_customer = dict(
            base_customer
        )

        test_customer[
            "behavior_profile"
        ] = profile

        activity_probability = (
            behavior_engine
            ._calculate_activity_probability(
                test_customer,
                simulation_day
            )
        )

        cart_probability = (
            behavior_engine
            ._calculate_add_to_cart_probability(
                test_customer
            )
        )

        purchase_probability = (
            behavior_engine
            ._calculate_purchase_probability(
                test_customer,
                simulation_day,
            )
        )

        results[profile] = {
            "activity": activity_probability,
            "cart": cart_probability,
            "purchase": purchase_probability
        }

        print(
            f"{profile}: "
            f"activity={activity_probability:.4f} | "
            f"cart={cart_probability:.4f} | "
            f"purchase={purchase_probability:.4f}"
        )


    assert (
        results["cautious"]["activity"]
        <
        results["balanced"]["activity"]
        <
        results["engaged"]["activity"]
    )

    assert (
        results["cautious"]["cart"]
        <
        results["balanced"]["cart"]
        <
        results["engaged"]["cart"]
    )

    assert (
        results["cautious"]["purchase"]
        <
        results["balanced"]["purchase"]
        <
        results["engaged"]["purchase"]
    )

    print(
        "\nBEHAVIORAL DIVERSITY CHECK PASSED."
    )

    print("\n" + "=" * 60)
    print("PROMOTION EFFECT CHECK")
    print("=" * 60)

    mattress = next(
        product
        for product in config["products"]
        if product["product_id"]
        == "PRD-MAT-001"
    )

    new_web_customer = {
        "lifetime_orders": 0,
        "acquisition_channel": "CH-WEB"
    }

    new_app_customer = {
        "lifetime_orders": 0,
        "acquisition_channel": "CH-APP"
    }

    existing_customer = {
        "lifetime_orders": 3,
        "acquisition_channel": "CH-WEB"
    }


    tests = [
        (
            "New customer - normal day",
            new_web_customer,
            10,
            mattress
        ),
        (
            "New app customer - normal day",
            new_app_customer,
            10,
            mattress
        ),
        (
            "Existing customer - normal day",
            existing_customer,
            10,
            mattress
        ),
        (
            "Existing customer - promo week",
            existing_customer,
            23,
            mattress
        ),
        (
            "Existing customer - after promo",
            existing_customer,
            26,
            mattress
        )
    ]


    for (
        label,
        customer,
        day,
        product
    ) in tests:

        multiplier = (
            behavior_engine
            ._get_promotion_multiplier(
                customer,
                day,
                product
            )
        )

        print(
            f"{label}: "
            f"multiplier={multiplier}"
        )

    print("\n" + "=" * 60)
    print("EVENT FUNNEL DISTRIBUTION CHECK")
    print("=" * 60)

    test_customer = customers[0]

    stage_counts = {
        "product_view": 0,
        "add_to_cart": 0,
        "purchase_intent": 0,
        "cart_abandonment": 0
    }

    iterations = 5000

    for _ in range(iterations):

        events = (
            behavior_engine
            .simulate_customer_day(
                customer=test_customer,
                simulation_day=10
            )
        )

        event_types = {
            event["event_type"]
            for event in events
        }

        for stage in stage_counts:

            if stage in event_types:
                stage_counts[stage] += 1


    for stage, count in stage_counts.items():

        print(
            f"{stage}: {count}"
        )


    views = stage_counts[
        "product_view"
    ]

    carts = stage_counts[
        "add_to_cart"
    ]

    intents = stage_counts[
        "purchase_intent"
    ]

    abandonments = stage_counts[
        "cart_abandonment"
    ]


    print(
        f"\nView -> Cart rate: "
        f"{carts / views:.4f}"
        if views
        else "View -> Cart rate: 0"
    )

    print(
        f"Cart -> Intent rate: "
        f"{intents / carts:.4f}"
        if carts
        else "Cart -> Intent rate: 0"
    )

    print(
        f"Cart abandonment rate: "
        f"{abandonments / carts:.4f}"
        if carts
        else "Cart abandonment rate: 0"
    )


    assert (
        views
        >= carts
        >= intents
    )

    assert (
        carts
        ==
        intents
        + abandonments
    )

    assert intents > 0

    assert abandonments > 0

    print(
        "\nEVENT FUNNEL DISTRIBUTION CHECK PASSED."
    )