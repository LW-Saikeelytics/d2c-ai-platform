import argparse
import time
import tracemalloc

from simulation.config_loader import load_all_config
from simulation.state import SimulationState

from simulation.customer_engine import CustomerEngine
from simulation.event_engine import EventEngine
from simulation.behavior_engine import BehaviorEngine
from simulation.conversion_engine import ConversionEngine
from simulation.order_engine import OrderEngine
from simulation.daily_simulation import DailySimulation

from validation.order_validator import OrderValidator


def run_scale_test(
    days,
    customer_count,
    scenario_name="baseline"
):

    print("=" * 60)
    print("SIMULATION SCALE VALIDATION")
    print("=" * 60)

    print(
        f"Scenario: {scenario_name}"
    )

    print(
        f"Simulation days: {days}"
    )

    print(
        f"Customers: {customer_count}"
    )

    # ======================================================
    # CONFIG + STATE
    # ======================================================

    config = load_all_config(
        scenario_name=scenario_name
    )

    state = SimulationState()

    # ======================================================
    # ENGINES
    # ======================================================

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

    order_engine = OrderEngine(
        config=config,
        simulation_state=state,
        customer_engine=customer_engine
    )

    order_validator = OrderValidator(
        config=config
    )

    simulation = DailySimulation(
        config=config,
        state=state,
        customer_engine=customer_engine,
        event_engine=event_engine,
        behavior_engine=behavior_engine,
        conversion_engine=conversion_engine,
        order_engine=order_engine,
        order_validator=order_validator
    )

    # ======================================================
    # CUSTOMER POPULATION
    # ======================================================

    customer_engine.generate_customer_population(
        count=customer_count,
        start_id=1,
        current_day=1
    )

    # ======================================================
    # RUN SIMULATION
    # ======================================================

    tracemalloc.start()

    start_time = time.perf_counter()

    results = simulation.run_days(
        start_day=1,
        end_day=days
    )

    elapsed_seconds = (
        time.perf_counter()
        - start_time
    )

    current_memory, peak_memory = (
        tracemalloc.get_traced_memory()
    )

    tracemalloc.stop()

    # ======================================================
    # METRICS
    # ======================================================

    total_orders = len(
        state.orders
    )

    total_events = len(
        state.events
    )

    total_behavior_events = len(
        state.behavior_history
    )

    total_conversions = sum(
        1
        for record
        in state.conversion_history
        if record[
            "result"
        ][
            "converted"
        ]
    )

    purchase_events = sum(
        1
        for event
        in state.events.values()
        if event.get(
            "event_type"
        ) == "purchase"
    )

    total_revenue = round(
        sum(
            order[
                "gross_amount"
            ]
            for order
            in state.orders.values()
        ),
        2
    )

    customer_days = (
        customer_count
        * days
    )

    customer_days_per_second = (
        customer_days
        / elapsed_seconds
        if elapsed_seconds > 0
        else 0
    )

    # ======================================================
    # VALIDATION
    # ======================================================

    print("\n" + "=" * 60)
    print("SCALE VALIDATION RESULTS")
    print("=" * 60)

    print(
        f"Current day: "
        f"{state.current_day}"
    )

    print(
        f"Daily metric rows: "
        f"{len(state.daily_metrics)}"
    )

    print(
        f"Customers: "
        f"{len(state.customers)}"
    )

    print(
        f"Orders: "
        f"{total_orders}"
    )

    print(
        f"Events: "
        f"{total_events}"
    )

    print(
        f"Behavior events: "
        f"{total_behavior_events}"
    )

    print(
        f"Successful conversions: "
        f"{total_conversions}"
    )

    print(
        f"Purchase events: "
        f"{purchase_events}"
    )

    print(
        f"Revenue: "
        f"{total_revenue:.2f}"
    )

    print(
        f"Customer-days processed: "
        f"{customer_days}"
    )

    print(
        f"Elapsed seconds: "
        f"{elapsed_seconds:.4f}"
    )

    print(
        f"Customer-days / second: "
        f"{customer_days_per_second:.2f}"
    )

    print(
        f"Peak Python memory: "
        f"{peak_memory / (1024 * 1024):.2f} MB"
    )

    # ------------------------------------------------------
    # Core durability checks
    # ------------------------------------------------------

    assert (
        state.current_day
        == days
    )

    assert (
        len(results)
        == days
    )

    assert (
        len(state.daily_metrics)
        == days
    )

    assert (
        len(state.customers)
        == customer_count
    )

    # ------------------------------------------------------
    # Counter reconciliation
    # ------------------------------------------------------

    assert (
        state.counters[
            "customer"
        ]
        == len(
            state.customers
        )
    )

    assert (
        state.counters[
            "order"
        ]
        == len(
            state.orders
        )
    )

    assert (
        state.counters[
            "event"
        ]
        == len(
            state.events
        )
    )

    # ------------------------------------------------------
    # Purchase/order reconciliation
    # ------------------------------------------------------

    assert (
        purchase_events
        == total_orders
    )

    # ------------------------------------------------------
    # Day-range checks
    # ------------------------------------------------------

    assert all(
        1
        <= order[
            "simulation_day"
        ]
        <= days
        for order
        in state.orders.values()
    )

    assert all(
        1
        <= event[
            "simulation_day"
        ]
        <= days
        for event
        in state.events.values()
    )

    # ------------------------------------------------------
    # Daily sequence check
    # ------------------------------------------------------

    metric_days = [
        metric[
            "simulation_day"
        ]
        for metric
        in state.daily_metrics
    ]

    assert (
        metric_days
        == list(
            range(
                1,
                days + 1
            )
        )
    )

    print(
        "\nSCALE VALIDATION PASSED."
    )


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--days",
        type=int,
        default=90
    )

    parser.add_argument(
        "--customers",
        type=int,
        default=500
    )

    parser.add_argument(
        "--scenario",
        default="baseline"
    )

    args = parser.parse_args()

    run_scale_test(
        days=args.days,
        customer_count=args.customers,
        scenario_name=args.scenario
    )