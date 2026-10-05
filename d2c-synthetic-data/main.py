from simulation.config_loader import load_all_config
from simulation.state import SimulationState
from simulation.customer_engine import CustomerEngine
from simulation.order_engine import OrderEngine
from validation.order_validator import OrderValidator
from simulation.bulk_order_engine import BulkOrderEngine
from simulation.daily_simulator import DailySimulator

def main():

    print("=" * 60)
    print("D2C SYNTHETIC DATA SIMULATOR")
    print("=" * 60)

    print("\n[1] Loading master data...")

    config = load_all_config()

    print("[2] Initializing simulation state...")

    state = SimulationState()

    print("[3] Initializing customer engine...")

    customer_engine = CustomerEngine(
        config=config,
        state=state,
        seed=42
    )

    print("[4] Initializing order engine...")

    order_engine = OrderEngine(
        config=config,
        simulation_state=state,
        customer_engine=customer_engine
    )

    print("\nFoundation loaded successfully.")

    print(f"Company: {config['company']['company_name']}")
    print(f"Simulation days: {config['company']['simulation_duration_days']}")
    print(f"Target orders/day: {config['company']['target_orders_per_day']}")

    print("\nCustomer engine initialized successfully.")

    customers = customer_engine.generate_customer_population(
        count=10,
        start_id=1,
        current_day=1
    )

    test_customer = customers[0]

    test_order = order_engine.generate_order(
        test_customer,
        simulation_day=1
    )

    print("\nGenerated test order:")
    print(test_order)

    print("\nValidating test order...")

    order_validator = OrderValidator(config)

    validation_result = order_validator.validate(
        test_order,
        test_customer
    )

    bulk_order_engine = BulkOrderEngine(
    order_engine,
    order_validator,
    customer_engine
    )

    daily_simulator = DailySimulator(
    config=config,
    state=state,
    customer_engine=customer_engine,
    bulk_order_engine=bulk_order_engine
    )

    if validation_result["valid"]:
        print("[OK] Test order passed validation")
    else:
        print("[ERROR] Test order failed validation")

    for error in validation_result["errors"]:
        print(f"  [ERROR] {error}")    

    print("\nGenerating Day 1 bulk orders...")

    bulk_result = bulk_order_engine.generate_orders(
        simulation_day=1,
        order_count=10
    )

    print("\nDay 1 bulk generation summary:")
    print(f"Requested: {bulk_result['requested']}")
    print(f"Generated: {bulk_result['generated']}")
    print(f"Valid:     {bulk_result['valid']}")
    print(f"Invalid:   {bulk_result['invalid']}")

    print("\nCustomer state after Day 1 orders:")

    customers = customer_engine.get_customers()

    for customer in customers[:5]:
        print({
            "customer_id": customer["customer_id"],
            "lifetime_orders": customer["lifetime_orders"],
            "lifetime_spend": customer["lifetime_spend"],
            "last_order_day": customer["last_order_day"]
        })

    print("\nRunning 3-day simulation...")

    daily_results = daily_simulator.run_days(
        start_day=1,
        end_day=3,
        orders_per_day=10
    )

    print("\nDaily simulation summary:")

    for result in daily_results:
        print(result)

    print("\nSimulation state:")
    print(f"Current day: {state.current_day}")
    print(f"Total valid orders: {len(state.orders)}")
    print(f"Total customers: {len(state.customers)}")

    print("\nGenerated customer population:")
    
    for customer in customers:
        print(customer)

    print("\nCustomers currently in simulation state:")
    print(len(state.customers))

    summary = customer_engine.summarize_population(
        customers
    )

    print("\nPopulation summary:")

    print("\nSegments:")
    print(summary["segments"])

    print("\nChannels:")
    print(summary["channels"])

    print("\nRegions:")
    print(summary["regions"])

    print("\n" + "=" * 60)
    print("STEP 2 FOUNDATION COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()