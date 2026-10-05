import random


class EventEngine:

    def __init__(self, config, state, seed=42):
        """
        Initialize the behavioral event engine.

        The Event Engine records customer interactions such as:
        - product views
        - add to cart
        - cart abandonment
        - purchases

        It does NOT create orders.
        Orders are still created by OrderEngine.
        """

        self.config = config
        self.state = state

        # Dedicated random generator so that
        # behavioral events remain reproducible.
        self.random = random.Random(seed)

    def _record_event(self, event):
        """
        Store one event inside SimulationState.

        Event IDs are generated centrally from the simulation state.
        """

        self.state.counters["event"] += 1

        event_id = f"EVT-{self.state.counters['event']:08d}"

        event["event_id"] = event_id

        self.state.events[event_id] = event

        return event

    def generate_product_view(
        self,
        customer,
        product,
        simulation_day
    ):
        """
        Generate a product_view event.
        """

        event = {
            "simulation_day": simulation_day,
            "customer_id": customer["customer_id"],
            "event_type": "product_view",
            "product_id": product["product_id"],
            "category": product["category"]
        }

        return self._record_event(event)

    def generate_add_to_cart(
        self,
        customer,
        product,
        simulation_day
    ):
        """
        Generate an add_to_cart event.
        """

        event = {
            "simulation_day": simulation_day,
            "customer_id": customer["customer_id"],
            "event_type": "add_to_cart",
            "product_id": product["product_id"],
            "category": product["category"]
        }

        return self._record_event(event)

    def generate_cart_abandonment(
        self,
        customer,
        product,
        simulation_day
    ):
        """
        Generate a cart_abandonment event.
        """

        event = {
            "simulation_day": simulation_day,
            "customer_id": customer["customer_id"],
            "event_type": "cart_abandonment",
            "product_id": product["product_id"],
            "category": product["category"]
        }

        return self._record_event(event)

    def generate_purchase_event(
        self,
        customer,
        order
    ):
        """
        Generate a purchase event for an existing order.

        IMPORTANT:
        This method does not create the order.
        It only records the behavioral event associated
        with an already-created order.
        """

        event = {
            "simulation_day": order["simulation_day"],
            "customer_id": customer["customer_id"],
            "event_type": "purchase",
            "product_id": order["product_id"],
            "category": order["category"],
            "order_id": order["order_id"]
        }

        return self._record_event(event)

    def generate_purchase_intent(
        self,
        customer_id,
        product,
        simulation_day
    ):
        event = {
            "simulation_day": simulation_day,
            "customer_id": customer_id,
            "event_type": "purchase_intent",
            "product_id": product["product_id"],
            "category": product["category"]
        }

        return self._record_event(event)

if __name__ == "__main__":

    from simulation.config_loader import load_all_config
    from simulation.state import SimulationState

    config = load_all_config()
    state = SimulationState()

    engine = EventEngine(
        config=config,
        state=state,
        seed=42
    )

    # Get one product from the frozen master data.
    product = config["products"][0]

    # Create a small test customer.
    customer = {
        "customer_id": "CUST-000001"
    }

    print("=" * 60)
    print("EVENT ENGINE TEST")
    print("=" * 60)

    view_event = engine.generate_product_view(
        customer=customer,
        product=product,
        simulation_day=1
    )

    print("\nProduct view:")
    print(view_event)

    cart_event = engine.generate_add_to_cart(
        customer=customer,
        product=product,
        simulation_day=1
    )

    print("\nAdd to cart:")
    print(cart_event)

    abandonment_event = engine.generate_cart_abandonment(
        customer=customer,
        product=product,
        simulation_day=1
    )

    print("\nCart abandonment:")
    print(abandonment_event)

    print("\nEvents stored in state:")
    print(len(state.events))

    print("\nEvent counter:")
    print(state.counters["event"])

    print("\nAll stored events:")

    for event_id, event in state.events.items():
        print(event)
