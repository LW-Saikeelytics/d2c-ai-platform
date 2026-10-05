from collections import defaultdict


class FunnelAnalytics:

    def __init__(self, state):
        self.state = state

    # ---------------------------------------------------------
    # BUILD EVENT STAGE DATA
    # ---------------------------------------------------------

    def _build_stage_data(self):

        event_counts = defaultdict(int)
        customer_sets = defaultdict(set)

        for event in self.state.events.values():

            event_type = event.get("event_type")
            customer_id = event.get("customer_id")

            if event_type is None:
                continue

            event_counts[event_type] += 1

            if customer_id is not None:
                customer_sets[event_type].add(
                    customer_id
                )

        return event_counts, customer_sets

    # ---------------------------------------------------------
    # SAFE RATE
    # ---------------------------------------------------------

    def _rate(self, numerator, denominator):

        if denominator == 0:
            return 0

        return round(
            numerator / denominator,
            4
        )

    # ---------------------------------------------------------
    # FUNNEL METRICS
    # ---------------------------------------------------------

    def calculate_funnel_metrics(self):

        (
            event_counts,
            customer_sets
        ) = self._build_stage_data()

        viewers = customer_sets[
            "product_view"
        ]

        cart_customers = customer_sets[
            "add_to_cart"
        ]

        intent_customers = customer_sets[
            "purchase_intent"
        ]

        purchasing_customers = customer_sets[
            "purchase"
        ]

        abandonment_customers = customer_sets[
            "cart_abandonment"
        ]

        # Customers who actually progressed
        # from one stage to the next.

        viewers_to_cart = (
            viewers
            & cart_customers
        )

        cart_to_intent = (
            cart_customers
            & intent_customers
        )

        viewers_to_purchase = (
            viewers
            & purchasing_customers
        )

        cart_to_purchase = (
            cart_customers
            & purchasing_customers
        )

        intent_to_purchase = (
            intent_customers
            & purchasing_customers
        )

        cart_with_abandonment = (
            cart_customers
            & abandonment_customers
        )

        return {

            # ---------------------------------------------
            # EVENT COUNTS
            # ---------------------------------------------

            "event_counts": {
                "product_views":
                    event_counts["product_view"],

                "add_to_cart":
                    event_counts["add_to_cart"],

                "purchase_intent":
                    event_counts["purchase_intent"],

                "cart_abandonment":
                    event_counts["cart_abandonment"],

                "purchases":
                    event_counts["purchase"]
            },

            # ---------------------------------------------
            # UNIQUE CUSTOMER STAGES
            # ---------------------------------------------

            "customer_stages": {
                "viewers":
                    len(viewers),

                "cart_customers":
                    len(cart_customers),

                "intent_customers":
                    len(intent_customers),

                "purchasing_customers":
                    len(purchasing_customers),

                "customers_with_abandonment":
                    len(abandonment_customers)
            },

            # ---------------------------------------------
            # CUSTOMER FUNNEL RATES
            # ---------------------------------------------

            "funnel_rates": {

                "view_to_cart_rate":
                    self._rate(
                        len(viewers_to_cart),
                        len(viewers)
                    ),

                "cart_to_intent_rate":
                    self._rate(
                        len(cart_to_intent),
                        len(cart_customers)
                    ),

                "view_to_purchase_rate":
                    self._rate(
                        len(viewers_to_purchase),
                        len(viewers)
                    ),

                "cart_to_purchase_rate":
                    self._rate(
                        len(cart_to_purchase),
                        len(cart_customers)
                    ),

                "intent_to_purchase_rate":
                    self._rate(
                        len(intent_to_purchase),
                        len(intent_customers)
                    ),

                "cart_abandonment_signal_rate":
                    self._rate(
                        len(cart_with_abandonment),
                        len(cart_customers)
                    )
            }
        }

    # ---------------------------------------------------------
    # RECONCILIATION
    # ---------------------------------------------------------

    def validate(self):

        event_counts, _ = (
            self._build_stage_data()
        )

        purchase_events = (
            event_counts["purchase"]
        )

        orders = len(
            self.state.orders
        )

        return {
            "purchase_events": purchase_events,
            "orders": orders,
            "purchase_order_match":
                purchase_events == orders
        }