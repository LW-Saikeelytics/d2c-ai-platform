import random
from datetime import date, timedelta


class CustomerEngine:

    def __init__(self, config, state, seed=42):
        self.config = config
        self.state = state

        # Dedicated random generator.
        # This makes the simulation reproducible.
        self.random = random.Random(seed)
        self.profile_random = random.Random(
            seed + 101
        )

    def _choose_behavior_profile(self):

        profiles = (
            self.config["company"].get(
                "behavior_profiles",
                {}
            )
        )

        if not profiles:
            return "balanced"

        profile_names = list(
            profiles.keys()
        )

        weights = [
            profiles[name].get(
                "weight",
                1
            )
            for name in profile_names
        ]

        return self.profile_random.choices(
            profile_names,
            weights=weights,
            k=1
        )[0]


    def get_behavior_profile_multiplier(
        self,
        customer,
        multiplier_name
    ):

        profile = customer.get(
            "behavior_profile",
            "balanced"
        )

        profiles = (
            self.config["company"].get(
                "behavior_profiles",
                {}
            )
        )

        profile_config = profiles.get(
            profile,
            {}
        )

        return profile_config.get(
            multiplier_name,
            1.00
        )        

    def generate_customer(self, customer_id, current_day=1):
        """
        Generate one customer using the frozen master data.

        This creates the customer's persistent profile.
        Purchase history will be added later by the Order Engine.
        """

        segment = self._choose_segment()
        city = self._choose_city()
        channel = self._choose_channel()

        registration_date = self._generate_registration_date(
            current_day
        )
        preferred_categories = (
            self._choose_preferred_categories(segment)
        )

        purchase_propensity = (
            self.calculate_purchase_propensity({
                "repeat_purchase_tendency":
                    segment["repeat_purchase_tendency"],
                "lifetime_orders": 0
            })
        )

        behavior_profile = (
            self._choose_behavior_profile()
        )

        customer = {
            "customer_id": customer_id,

            "segment": segment["segment_id"],

            "price_tendency": segment["price_tendency"],

            "discount_sensitivity": segment["discount_sensitivity"],

            "premium_product_tendency": segment[
                "premium_product_tendency"
            ],

            "repeat_purchase_tendency": segment[
                "repeat_purchase_tendency"
            ],

            "city_id": city["city_id"],

            "region": city["region"],

            "acquisition_channel": channel["channel_id"],

            "registration_day": registration_date,

            "lifetime_orders": 0,

            "lifetime_spend": 0.0,

            "last_order_day": None,

            "preferred_categories": preferred_categories,

            "purchase_propensity": purchase_propensity,
            "behavior_profile": behavior_profile,
            "status": "active"
        }

        self.state.customers[customer_id] = customer
        self.state.counters["customer"] += 1
        
        return customer

    def generate_customer_population(self, count, start_id=1, current_day=1):
        """
        Generate and store multiple customers.

        Returns the list of generated customer records.
        """

        customers = []

        for number in range(start_id, start_id + count):

            customer_id = f"CUST-{number:06d}"

            customer = self.generate_customer(
                customer_id=customer_id,
                current_day=current_day
            )

            customers.append(customer)

        return customers

    def _choose_preferred_categories(self, segment):
        """
        Assign a small set of preferred product categories
        based on the customer's behavioural segment.
        """

        products = self.config["products"]

        categories = sorted(
            set(product["category"] for product in products)
        )

        preference_weights = {
            "SEG-001": {
                "Mattresses": 3,
                "Pillows": 3,
                "Bedding": 3,
                "Sleep Accessories": 4,
                "Beds": 1,
                "Sofas": 1,
                "Recliners": 1
            },

            "SEG-002": {
                "Mattresses": 4,
                "Beds": 3,
                "Sofas": 3,
                "Pillows": 2,
                "Bedding": 2,
                "Sleep Accessories": 2,
                "Recliners": 2
            },

            "SEG-003": {
                "Mattresses": 4,
                "Beds": 4,
                "Sofas": 3,
                "Recliners": 3,
                "Pillows": 2,
                "Bedding": 2,
                "Sleep Accessories": 1
            },

            "SEG-004": {
                "Mattresses": 3,
                "Pillows": 3,
                "Bedding": 3,
                "Sleep Accessories": 3,
                "Beds": 2,
                "Sofas": 2,
                "Recliners": 2
            },

            "SEG-005": {
                "Mattresses": 3,
                "Pillows": 3,
                "Bedding": 3,
                "Sleep Accessories": 3,
                "Beds": 2,
                "Sofas": 2,
                "Recliners": 1
            }
        }

        weights_map = preference_weights.get(
            segment["segment_id"],
            {}
        )

        weights = [
            weights_map.get(category, 1)
            for category in categories
        ]

        preference_count = self.random.randint(1, 3)

        selected = []

        available_categories = categories.copy()

        for _ in range(preference_count):

            available_weights = [
                weights_map.get(category, 1)
                for category in available_categories
            ]

            chosen = self.random.choices(
                available_categories,
                weights=available_weights,
                k=1
            )[0]

            selected.append(chosen)
            available_categories.remove(chosen)

        return selected

    def summarize_population(self, customers):
        """
        Summarize the generated customer population.
        """

        segment_counts = {}
        city_counts = {}
        channel_counts = {}
        region_counts = {}

        for customer in customers:

            segment = customer["segment"]
            city = customer["city_id"]
            channel = customer["acquisition_channel"]
            region = customer["region"]

            segment_counts[segment] = (
                segment_counts.get(segment, 0) + 1
            )

            city_counts[city] = (
                city_counts.get(city, 0) + 1
            )

            channel_counts[channel] = (
                channel_counts.get(channel, 0) + 1
            )

            region_counts[region] = (
                region_counts.get(region, 0) + 1
            )

        return {
            "total_customers": len(customers),
            "segments": segment_counts,
            "cities": city_counts,
            "channels": channel_counts,
            "regions": region_counts
        }

    def _choose_segment(self):
        segments = self.config["customer_segments"]

        weights = []

        for segment in segments:
            share = segment.get("baseline_share", "medium")

            if share == "high":
                weight = 3
            elif share == "low":
                weight = 1
            else:
                weight = 2

            weights.append(weight)

        return self.random.choices(
            segments,
            weights=weights,
            k=1
        )[0]

    def _choose_city(self):
        cities = self.config["cities"]

        return self.random.choice(cities)

    def _choose_channel(self):
        channels = self.config["channels"]

        weights = []

        for channel in channels:
            share = channel.get("baseline_share", "medium")

            if share == "high":
                weight = 3
            elif share == "low":
                weight = 1
            else:
                weight = 2

            weights.append(weight)

        return self.random.choices(
            channels,
            weights=weights,
            k=1
        )[0]

    def _generate_registration_date(self, current_day):
        """
        Customers can exist before the simulation starts,
        allowing us to simulate an existing customer base.

        A customer generated on Day N may therefore have
        registered before Day N.
        """

        max_history_days = 365

        history_days = self.random.randint(
            0,
            max_history_days
        )

        registration_day = current_day - history_days

        return registration_day

    def calculate_purchase_propensity(self, customer):
        """
        Calculate the customer's baseline probability of
        placing an order on a given simulation day.

        This is a baseline behavioural signal.
        Business events will influence demand later.
        """

        repeat_tendency = customer[
            "repeat_purchase_tendency"
        ]

        propensity_map = {
            "high": 0.30,
            "medium": 0.18,
            "low": 0.08
        }

        propensity = propensity_map.get(
            repeat_tendency,
            0.15
        )

        # Newer customers are slightly less likely
        # to repeat immediately.
        if customer["lifetime_orders"] == 0:
            propensity *= 0.75

        return round(propensity, 4)

    def get_customers(self):
        return list(self.state.customers.values())

    def select_customer_for_order(self, customers):

        weights = []

        for customer in customers:

            propensity = customer.get(
                "purchase_propensity",
                0.1
            )

            weights.append(max(propensity, 0.001))

        return self.random.choices(
            customers,
            weights=weights,
            k=1
        )[0]

    def record_purchase(self, customer, order):

        customer["lifetime_orders"] += 1

        customer["lifetime_spend"] = round(
            customer["lifetime_spend"]
            + order["gross_amount"],
            2
        )

        customer["last_order_day"] = order[
            "simulation_day"
        ]

    def get_lifecycle_stage(
        self,
        customer,
        simulation_day
    ):

        lifecycle_config = (
            self.config["company"].get(
                "customer_lifecycle",
                {}
            )
        )

        new_prospect_days = (
            lifecycle_config.get(
                "new_prospect_days",
                30
            )
        )

        recent_buyer_days = (
            lifecycle_config.get(
                "recent_buyer_days",
                7
            )
        )

        active_buyer_days = (
            lifecycle_config.get(
                "active_buyer_days",
                30
            )
        )

        at_risk_days = (
            lifecycle_config.get(
                "at_risk_days",
                60
            )
        )

        lifetime_orders = customer.get(
            "lifetime_orders",
            0
        )

        # --------------------------------------------------
        # NEVER PURCHASED
        # --------------------------------------------------

        if lifetime_orders == 0:

            registration_day = customer.get(
                "registration_day",
                simulation_day
            )

            customer_age = max(
                simulation_day
                - registration_day,
                0
            )

            if customer_age <= new_prospect_days:
                return "new_prospect"

            return "established_prospect"

        # --------------------------------------------------
        # EXISTING CUSTOMER
        # --------------------------------------------------

        last_order_day = customer.get(
            "last_order_day"
        )

        if last_order_day is None:
            return "established_prospect"

        days_since_purchase = max(
            simulation_day
            - last_order_day,
            0
        )

        if days_since_purchase <= recent_buyer_days:
            return "recent_buyer"

        if days_since_purchase <= active_buyer_days:
            return "active_buyer"

        if days_since_purchase <= at_risk_days:
            return "at_risk"

        return "dormant"

    def get_lifecycle_activity_multiplier(
        self,
        customer,
        simulation_day
    ):

        lifecycle_stage = (
            self.get_lifecycle_stage(
                customer,
                simulation_day
            )
        )

        multipliers = (
            self.config["company"]
            .get(
                "customer_lifecycle",
                {}
            )
            .get(
                "activity_multipliers",
                {}
            )
        )

        return multipliers.get(
            lifecycle_stage,
            1.00
        )

    def get_customer_activity_status(
        self,
        customer,
        simulation_day
    ):

        churn_config = (
            self.config["company"].get(
                "churn_behavior",
                {}
            )
        )

        inactive_after_days = (
            churn_config.get(
                "inactive_after_days",
                45
            )
        )

        churned_after_days = (
            churn_config.get(
                "churned_after_days",
                90
            )
        )

        last_order_day = customer.get(
            "last_order_day"
        )

        registration_day = customer.get(
            "registration_day",
            simulation_day
        )

        # Use last purchase when available.
        # Otherwise use registration as the last known activity anchor.
        activity_anchor = (
            last_order_day
            if last_order_day is not None
            else registration_day
        )

        days_inactive = max(
            simulation_day
            - activity_anchor,
            0
        )

        if days_inactive >= churned_after_days:
            return "churned"

        if days_inactive >= inactive_after_days:
            return "inactive"

        return "active"

    def get_churn_activity_multiplier(
        self,
        customer,
        simulation_day
    ):

        status = (
            self.get_customer_activity_status(
                customer,
                simulation_day
            )
        )

        multipliers = (
            self.config["company"]
            .get(
                "churn_behavior",
                {}
            )
            .get(
                "activity_multipliers",
                {}
            )
        )

        return multipliers.get(
            status,
            1.00
        )

    def get_product_price_weight(
        self,
        customer,
        product
    ):

        price_tendency = customer.get(
            "price_tendency",
            "medium"
        )

        price_band = product.get(
            "price_band",
            "Mid"
        )

        preference_weights = (
            self.config["company"].get(
                "price_band_preference_weights",
                {}
            )
        )

        tendency_weights = (
            preference_weights.get(
                price_tendency,
                {}
            )
        )

        return tendency_weights.get(
            price_band,
            1
        )

    def get_product_popularity_weight(
        self,
        product
    ):

        popularity_config = (
            self.config["company"].get(
                "product_popularity",
                {}
            )
        )

        default_weight = (
            popularity_config.get(
                "default_weight",
                1.00
            )
        )

        overrides = (
            popularity_config.get(
                "overrides",
                {}
            )
        )

        product_id = product.get(
            "product_id"
        )

        return overrides.get(
            product_id,
            default_weight
        )

    def get_product_selection_weight(
        self,
        customer,
        product
    ):

        price_weight = (
            self.get_product_price_weight(
                customer,
                product
            )
        )

        popularity_weight = (
            self.get_product_popularity_weight(
                product
            )
        )

        inventory_weight = (
            self.get_product_inventory_weight(
                customer,
                product
            )
        )

        return (
            price_weight
            * popularity_weight
            * inventory_weight
        )

    def get_serving_warehouses(
        self,
        customer
    ):

        customer_region = customer.get(
            "region"
        )

        return [
            warehouse
            for warehouse in self.config["warehouses"]
            if customer_region
            in warehouse.get(
                "service_regions",
                []
            )
        ]

    def get_product_inventory_status(
        self,
        customer,
        product
    ):

        inventory_config = (
            self.config["company"].get(
                "inventory_behavior",
                {}
            )
        )

        default_status = (
            inventory_config.get(
                "default_status",
                "in_stock"
            )
        )

        customer_region = customer.get(
            "region"
        )

        # --------------------------------------------------
        # Backward compatibility / lightweight test fixtures
        # --------------------------------------------------
        #
        # Some unit tests intentionally use partial customer
        # dictionaries without geography.
        #
        # In that case inventory should not invalidate every
        # product.
        # --------------------------------------------------

        if not customer_region:
            return default_status

        serving_warehouses = (
            self.get_serving_warehouses(
                customer
            )
        )

        # A real region exists, but no warehouse can service it.
        if not serving_warehouses:
            return "out_of_stock"

        regional_overrides = (
            inventory_config.get(
                "regional_overrides",
                {}
            )
        )

        region_inventory = (
            regional_overrides.get(
                customer_region,
                {}
            )
        )

        return region_inventory.get(
            product.get("product_id"),
            default_status
        )

    def get_product_inventory_weight(
        self,
        customer,
        product
    ):

        inventory_status = (
            self.get_product_inventory_status(
                customer,
                product
            )
        )

        status_multipliers = (
            self.config["company"]
            .get(
                "inventory_behavior",
                {}
            )
            .get(
                "status_multipliers",
                {}
            )
        )

        return status_multipliers.get(
            inventory_status,
            1.00
        )

if __name__ == "__main__":

    from simulation.config_loader import load_all_config
    from simulation.state import SimulationState

    config = load_all_config()
    state = SimulationState()

    engine = CustomerEngine(
        config=config,
        state=state,
        seed=42
    )

    customer = engine.generate_customer(
        customer_id="CUST-000001",
        current_day=1
    )

    print("\nGenerated Customer:")
    print(customer)    

    print("\n" + "=" * 60)
    print("CUSTOMER LIFECYCLE CHECK")
    print("=" * 60)

    simulation_day = 70

    test_customers = [
        {
            "label": "New prospect",
            "registration_day": 60,
            "lifetime_orders": 0,
            "last_order_day": None
        },
        {
            "label": "Established prospect",
            "registration_day": 1,
            "lifetime_orders": 0,
            "last_order_day": None
        },
        {
            "label": "Recent buyer",
            "registration_day": 1,
            "lifetime_orders": 1,
            "last_order_day": 67
        },
        {
            "label": "Active buyer",
            "registration_day": 1,
            "lifetime_orders": 2,
            "last_order_day": 50
        },
        {
            "label": "At risk",
            "registration_day": 1,
            "lifetime_orders": 2,
            "last_order_day": 30
        },
        {
            "label": "Dormant",
            "registration_day": 1,
            "lifetime_orders": 2,
            "last_order_day": 1
        }
    ]

    for test_customer in test_customers:

        stage = engine.get_lifecycle_stage(
            test_customer,
            simulation_day
        )

        multiplier = (
            engine
            .get_lifecycle_activity_multiplier(
                test_customer,
                simulation_day
            )
        )

        print(
            f"{test_customer['label']}: "
            f"{stage} | "
            f"multiplier={multiplier}"
        )

    print("\n" + "=" * 60)
    print("CHURN / INACTIVITY CHECK")
    print("=" * 60)

    simulation_day = 120

    test_cases = [
        ("Recently active", 110),
        ("Inactive customer", 60),
        ("Churned customer", 20)
    ]

    for label, last_order_day in test_cases:

        test_customer = {
            "registration_day": 1,
            "last_order_day": last_order_day
        }

        status = (
            engine.get_customer_activity_status(
                test_customer,
                simulation_day
            )
        )

        multiplier = (
            engine.get_churn_activity_multiplier(
                test_customer,
                simulation_day
            )
        )

        print(
            f"{label}: "
            f"{status} | "
            f"multiplier={multiplier}"
        )