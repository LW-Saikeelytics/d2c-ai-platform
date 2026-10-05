from asyncio import events
import argparse
import json

from simulation.config_loader import load_all_config
from simulation.state import SimulationState

from simulation.customer_engine import CustomerEngine
from simulation.event_engine import EventEngine
from simulation.behavior_engine import BehaviorEngine
from simulation.conversion_engine import ConversionEngine
from simulation.order_engine import OrderEngine

from validation.order_validator import OrderValidator
from exporters.dataset_writer import DatasetWriter
from validation.cross_table_validator import CrossTableValidator 
from validation.dataset_quality_validator import DatasetQualityValidator
from validation.business_rule_validator import BusinessRuleValidator
from validation.statistical_quality_validator import (
    StatisticalQualityValidator
)
from analytics.daily_analytics import DailyAnalytics
from analytics.quality_report import DatasetQualityReport
from analytics.multi_day_analytics import MultiDayAnalytics
from validation.schema_validator import (
    SimulationDatasetSchemaValidator
)
from validation.categorical_value_validator import (
    CategoricalValueValidator
)

from analytics.business_kpis import (BusinessKPIAnalytics)
from analytics.product_analytics import (ProductAnalytics)
from analytics.retention_analytics import (RetentionAnalytics)
from analytics.funnel_analytics import (FunnelAnalytics)
from analytics.period_analytics import (PeriodAnalytics)
from analytics.analytics_tables import (AnalyticsTableBuilder)
from exporters.analytics_writer import (AnalyticsDatasetWriter)
from validation.analytics_dataset_validator import (AnalyticsDatasetValidator)

class DailySimulation:

    def __init__(
        self,
        config,
        state,
        customer_engine,
        event_engine,
        behavior_engine,
        conversion_engine,
        order_engine,
        order_validator
    ):
        """
        Central orchestrator for one simulation day.

        Responsibilities:
        - run customer behaviour
        - evaluate conversion
        - create orders for converted customers
        - validate generated orders
        - store valid orders
        - record purchase events
        - update customer state

        Business logic remains inside the individual engines.
        """

        self.config = config
        self.state = state

        self.customer_engine = customer_engine
        self.event_engine = event_engine
        self.behavior_engine = behavior_engine
        self.conversion_engine = conversion_engine
        self.order_engine = order_engine
        self.order_validator = order_validator

    def run_day(self, simulation_day):
        """
        Run one complete simulation day.
        """

        self.state.current_day = simulation_day
        self.state.reset_daily_state()

        customers = self.customer_engine.get_customers()

        all_behavior_events = []
        conversion_results = []

        generated_orders = []
        valid_orders = []
        invalid_orders = []

        purchase_events = []

        # ==================================================
        # STEP 1
        # Simulate customer behaviour
        # ==================================================

        for customer in customers:

            events = self.behavior_engine.simulate_customer_day(
                customer=customer,
                simulation_day=simulation_day
            )

            if not events:
                continue

            all_behavior_events.extend(events)

            self.state.daily_behaviors.extend(events)
            self.state.behavior_history.extend(events)
            self.state.daily_events.extend(events)

            # ==============================================
            # STEP 2
            # Evaluate conversion
            # ==============================================

            conversion = self.conversion_engine.should_convert(
                customer=customer,
                events=events
            )

            conversion_record = {
                "simulation_day": simulation_day,
                "customer_id": customer["customer_id"],
                "result": conversion
            }

            conversion_results.append(
            conversion_record
            )

            self.state.daily_conversions.append(
            conversion_record
            )

            self.state.conversion_history.append(
            conversion_record
            )

            if not conversion["converted"]:
                continue

            # ==============================================
            # STEP 3
            # Get conversion product
            # ==============================================

            product = self.conversion_engine.get_conversion_product(
                events
            )

            if product is None:
                continue

            # ==============================================
            # STEP 4
            # Generate actual order
            # ==============================================

            order = self._generate_order(
                customer=customer,
                product=product,
                simulation_day=simulation_day
            )

            if order is None:
                continue

            generated_orders.append(order)

            # ==============================================
            # STEP 5
            # Validate order
            # ==============================================

            validation_result = self._validate_order(
                order=order,
                customer=customer
            )

            if not validation_result["valid"]:

                invalid_orders.append({
                    "order": order,
                    "validation": validation_result
                })

                continue

            # ==============================================
            # STEP 6
            # Store valid order
            # ==============================================

            valid_orders.append(order)

            self.state.orders[order["order_id"]] = order
            self.state.counters["order"] += 1

            self.state.daily_orders.append(order)

            # ==============================================
            # STEP 7
            # Update customer state
            # ==============================================

            self.customer_engine.record_purchase(
                customer=customer,
                order=order
            )

            # ==============================================
            # STEP 8
            # Record purchase event
            # ==============================================

            purchase_event = (
                self.event_engine.generate_purchase_event(
                    customer=customer,
                    order=order
                )
            )

            purchase_events.append(
                purchase_event
            )

            self.state.daily_events.append(
                purchase_event
            )

        # ==================================================
        # DAY SUMMARY
        # ==================================================

        daily_summary = {
            "simulation_day": simulation_day,

            "customers": len(customers),

            "behavior_events": {
                "customers_with_events": len({
                    event["customer_id"]
                    for event in all_behavior_events
                }),

                "total_events": len(
                    all_behavior_events
                )
            },

            "conversion": {
                "customers_evaluated": len(
                    conversion_results
                ),

                "conversions": sum(
                    1
                    for result in conversion_results
                    if result["result"]["converted"]
                )
            },

            "orders": {
                "generated_orders": len(
                    generated_orders
                ),

                "valid_orders": len(
                    valid_orders
                ),

                "invalid_orders": len(
                    invalid_orders
                )
            },

            "purchase_events": len(
                purchase_events
            )
        }

        self.state.daily_metrics.append(
            daily_summary
        )

        return daily_summary

    def run_days(self, start_day, end_day):
        """
        Run the simulation across multiple consecutive days.
        """

        daily_results = []

        for day in range(start_day, end_day + 1):

            result = self.run_day(
                simulation_day=day
            )

            daily_results.append(result)

        return daily_results

    # ======================================================
    # ORDER GENERATION
    # ======================================================

    def _generate_order(
        self,
        customer,
        product,
        simulation_day
    ):
        """
        Generate an order using the existing OrderEngine.

        The OrderEngine remains responsible for constructing
        the actual transaction.
        """

        order = self.order_engine.generate_order(
            customer=customer,
            simulation_day=simulation_day
        )

        return order

    # ======================================================
    # ORDER VALIDATION
    # ======================================================

    def _validate_order(
        self,
        order,
        customer
    ):
        """
        Validate an order using the existing OrderValidator.
        """

        result = self.order_validator.validate(
            order,
            customer=customer
        )

        # ----------------------------------------------
        # Normalise validator output
        # ----------------------------------------------

        if isinstance(result, bool):

            return {
                "valid": result
            }

        if isinstance(result, dict):

            if "valid" in result:
                return result

            if "is_valid" in result:

                return {
                    "valid": result["is_valid"],
                    **result
                }

        return {
            "valid": bool(result)
        }


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=(
            "Run the D2C synthetic "
            "business simulation."
        )
    )

    parser.add_argument(
        "--scenario",
        default="baseline",
        help=(
            "Simulation scenario to run."
        )
    )

    args = parser.parse_args()

    print("=" * 60)
    print("DAILY SIMULATION TEST")
    print("=" * 60)

    # ------------------------------------------------------
    # Load foundation
    # ------------------------------------------------------

    print("\n[1] Loading master data...")

    config = load_all_config(
        scenario_name=args.scenario
    )

    scenario = config[
        "scenario"
    ]

    print(
        f"Scenario: "
        f"{scenario['name']}"
    )

    print(
        f"Scenario description: "
        f"{scenario['description']}"
    )

    print("[2] Initializing simulation state...")

    state = SimulationState()

    # ------------------------------------------------------
    # Customer Engine
    # ------------------------------------------------------

    print("[3] Initializing customer engine...")

    customer_engine = CustomerEngine(
        config=config,
        state=state,
        seed=42
    )

    customers = customer_engine.generate_customer_population(
        count=10,
        start_id=1,
        current_day=1
    )

    print(
        f"Generated customers: {len(customers)}"
    )

    # ------------------------------------------------------
    # Event Engine
    # ------------------------------------------------------

    print("[4] Initializing event engine...")

    event_engine = EventEngine(
        config=config,
        state=state,
        seed=42
    )

    # ------------------------------------------------------
    # Behavior Engine
    # ------------------------------------------------------

    print("[5] Initializing behavior engine...")

    behavior_engine = BehaviorEngine(
        config=config,
        state=state,
        customer_engine=customer_engine,
        event_engine=event_engine,
        seed=42
    )

    # ------------------------------------------------------
    # Conversion Engine
    # ------------------------------------------------------

    print("[6] Initializing conversion engine...")

    conversion_engine = ConversionEngine(
        config=config,
        state=state,
        seed=42
    )

    # ------------------------------------------------------
    # Order Engine
    # ------------------------------------------------------

    print("[7] Initializing order engine...")

    order_engine = OrderEngine(
        config=config,
        simulation_state=state,
        customer_engine=customer_engine
    )

    # ------------------------------------------------------
    # Order Validator
    # ------------------------------------------------------

    print("[8] Initializing order validator...")

    order_validator = OrderValidator(
        config=config
    )

    # ------------------------------------------------------
    # Daily Simulation
    # ------------------------------------------------------

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

    # ------------------------------------------------------
    # Run Day 1
    # ------------------------------------------------------

    print("\n" + "=" * 60)
    print("RUNNING DAY 1")
    print("=" * 60)

    result = simulation.run_day(
        simulation_day=1
    )

    # ------------------------------------------------------
    # Print results
    # ------------------------------------------------------

    print("\nDaily simulation summary:")

    print(
        "Simulation day:",
        result["simulation_day"]
    )

    print(
        "Customers:",
        result["customers"]
    )

    print("\nBehaviour:")

    print(
        "Customers with events:",
        result["behavior_events"][
            "customers_with_events"
        ]
    )

    print(
        "Total events:",
        result["behavior_events"][
            "total_events"
        ]
    )

    print("\nConversion:")

    print(
        "Customers evaluated:",
        result["conversion"][
            "customers_evaluated"
        ]
    )

    print(
        "Conversions:",
        result["conversion"][
            "conversions"
        ]
    )

    print("\nOrders:")

    print(
        "Generated:",
        result["orders"][
            "generated_orders"
        ]
    )

    print(
        "Valid:",
        result["orders"][
            "valid_orders"
        ]
    )

    print(
        "Invalid:",
        result["orders"][
            "invalid_orders"
        ]
    )

    print("\nPurchase events:")

    print(
        result["purchase_events"]
    )

    print("\nSimulation state:")

    print(
        "Current day:",
        state.current_day
    )

    print(
        "Customers:",
        len(state.customers)
    )

    print(
        "Orders:",
        len(state.orders)
    )

    print(
        "Events:",
        len(state.events)
    )

    print(
        "Daily behaviors:",
        len(state.daily_behaviors)
    )

    print(
        "Behavior history:",
        len(state.behavior_history)
    )

    print(
        "Daily conversions:",
        len(state.daily_conversions)
    )

    print(
        "Conversion history:",
        len(state.conversion_history)
    )

    print(
        "Daily orders:",
        len(state.daily_orders)
    )

    print(
        "Daily events:",
        len(state.daily_events)
    )

    print(
        "Daily metrics:",
        len(state.daily_metrics)
    )

    day_1_behavior_history_count = len(
        state.behavior_history
    )

    day_1_conversion_history_count = len(
        state.conversion_history
    )

    day_1_order_count = len(
        state.orders
    )

    day_1_event_count = len(
        state.events
    )

    print("\n" + "=" * 60)
    print("DAY 1 COMPLETE")
    print("=" * 60)


    print("\n" + "=" * 60)
    print("RUNNING DAY 2")
    print("=" * 60)

    result_day_2 = simulation.run_day(
        simulation_day=2
    )

    print("\nDay 2 simulation summary:")

    print(
        "Simulation day:",
        result_day_2["simulation_day"]
    )

    print(
        "Customers:",
        result_day_2["customers"]
    )

    print(
        "Total orders in state:",
        len(state.orders)
    )

    print(
        "Daily orders:",
        len(state.daily_orders)
    )

    print(
        "Total events in state:",
        len(state.events)
    )

    print(
        "Daily events:",
        len(state.daily_events)
    )

    print(
        "Behavior history:",
        len(state.behavior_history)
    )

    print(
        "Conversion history:",
        len(state.conversion_history)
    )

    print(
        "Daily metrics:",
        len(state.daily_metrics)
    )

    print("\n" + "=" * 60)
    print("DAY 2 COMPLETE")
    print("=" * 60)

    print("\nCustomer purchase state:")

    for customer in customer_engine.get_customers():

        if customer.get("lifetime_orders", 0) > 0:

            print(
                customer["customer_id"],
                "| Lifetime orders:",
                customer.get("lifetime_orders"),
                "| Lifetime spend:",
                customer.get("lifetime_spend"),
                "| Last order day:",
                customer.get("last_order_day")
            )

    print("\nRunning persistence validation...")

    assert state.current_day == 2, (
        "Current simulation day should be 2."
    )

    assert len(state.daily_metrics) == 2, (
        "Daily metrics should contain exactly 2 days."
    )

    assert len(state.customers) == 10, (
        "Customer population should persist across days."
    )

    assert len(state.behavior_history) >= len(state.daily_behaviors), (
        "Behavior history should contain current and previous day behavior."
    )

    assert len(state.conversion_history) >= len(state.daily_conversions), (
        "Conversion history should contain current and previous day conversions."
    )

    assert len(state.events) >= len(state.daily_events), (
        "Event history should contain current and previous day events."
    )

    assert len(state.orders) >= len(state.daily_orders), (
        "Order history should contain current and previous day orders."
    )

    assert len(state.behavior_history) >= day_1_behavior_history_count, (
        "Day 1 behavior history was lost after Day 2."
    )

    assert len(state.conversion_history) >= day_1_conversion_history_count, (
        "Day 1 conversion history was lost after Day 2."
    )

    assert len(state.orders) >= day_1_order_count, (
        "Day 1 orders were lost after Day 2."
    )

    assert len(state.events) >= day_1_event_count, (
        "Day 1 events were lost after Day 2."
    ) 

    print("Persistence validation PASSED.")

    print("\n" + "=" * 60)
    print("TESTING MULTI-DAY RUNNER")
    print("=" * 60)

    multi_day_results = simulation.run_days(
        start_day=3,
        end_day=5
    )

    print("\nMulti-day results:")

    for day_result in multi_day_results:
        print(
            "Day:",
            day_result["simulation_day"],
            "| Customers:",
            day_result["customers"],
            "| Valid orders:",
            day_result["orders"]["valid_orders"],
            "| Events:",
            day_result["behavior_events"]["total_events"]
        )

    print("\nFinal simulation state:")

    print(
        "Current day:",
        state.current_day
    )

    print(
        "Daily metrics:",
        len(state.daily_metrics)
    )

    print(
        "Total orders:",
        len(state.orders)
    )

    print(
        "Total events:",
        len(state.events)
    )

    print("\nRunning multi-day validation...")

    assert state.current_day == 5, (
        "Simulation should end on Day 5."
    )

    assert len(state.daily_metrics) == 5, (
        "Daily metrics should contain exactly 5 days."
    )

    assert len(multi_day_results) == 3, (
        "Multi-day runner should return 3 daily results."
    )

    assert [
        result["simulation_day"]
        for result in multi_day_results
    ] == [3, 4, 5], (
        "Multi-day runner returned incorrect simulation days."
    )

    print("Multi-day validation PASSED.")

    print("\n" + "=" * 60)
    print("CONTINUING TO DAY 7")
    print("=" * 60)

    week_results = simulation.run_days(
        start_day=6,
        end_day=7
    )

    for day_result in week_results:
        print(
            "Day:",
            day_result["simulation_day"],
            "| Customers:",
            day_result["customers"],
            "| Valid orders:",
            day_result["orders"]["valid_orders"],
            "| Events:",
            day_result["behavior_events"]["total_events"]
        )

    print("\n7-day simulation state:")

    print(
        "Current day:",
        state.current_day
    )

    print(
        "Daily metrics:",
        len(state.daily_metrics)
    )

    print(
        "Total orders:",
        len(state.orders)
    )

    print(
        "Total events:",
        len(state.events)
    )

    print("\nRunning 7-day validation...")

    assert state.current_day == 7, (
        "Simulation should end on Day 7."
    )

    assert len(state.daily_metrics) == 7, (
        "Daily metrics should contain exactly 7 days."
    )

    assert len(week_results) == 2, (
        "Final continuation should return Days 6 and 7."
    )

    assert [
        result["simulation_day"]
        for result in week_results
    ] == [6, 7], (
        "Final continuation returned incorrect simulation days."
    )

    print("7-day validation PASSED.")

    # ============================================================
    # CONTINUE SIMULATION TO DAY 30
    # ============================================================

    print("\n" + "=" * 60)
    print("CONTINUING TO DAY 30")
    print("=" * 60)

    results_30_day_extension = simulation.run_days(
        start_day=8,
        end_day=30
    )

    for result in results_30_day_extension:
        print(
            "Day:",
            result["simulation_day"],
            "| Customers:",
            result["customers"],
            "| Valid orders:",
            result["orders"]["valid_orders"],
            "| Events:",
            result["behavior_events"]["total_events"]
        )

    print("\n30-day simulation state:")

    print(
        "Current day:",
        state.current_day
    )

    print(
        "Daily metrics:",
        len(state.daily_metrics)
    )

    print(
        "Total orders:",
        len(state.orders)
    )

    print(
        "Total events:",
        len(state.events)
    )

    print("\nRunning 30-day validation...")

    assert state.current_day == 30, (
        "Simulation should end on Day 30."
    )

    assert len(state.daily_metrics) == 30, (
        "Daily metrics should contain exactly 30 days."
    )

    assert len(results_30_day_extension) == 23, (
        "30-day continuation should return Days 8 through 30."
    )

    assert [
        result["simulation_day"]
        for result in results_30_day_extension
    ] == list(range(8, 31)), (
        "30-day continuation returned incorrect simulation days."
    )

    print("30-day validation PASSED.")

    print("\n" + "=" * 60)
    print("RUNNING DATASET QUALITY VALIDATION")
    print("=" * 60)

    dataset_validator = DatasetQualityValidator(state)

    quality_result = dataset_validator.validate_all()

    print(quality_result)

    # print("\n" + "=" * 60)
    # print("DATASET SCHEMA SAMPLES")
    # print("=" * 60)

    # if state.customers:
    #     first_customer = next(iter(state.customers.values()))
    #     print("\nCUSTOMER:")
    #     print(first_customer)

    # if state.orders:
    #     first_order = next(iter(state.orders.values()))
    #     print("\nORDER:")
    #     print(first_order)

    # if state.events:
    #     first_event = next(iter(state.events.values()))
    #     print("\nEVENT:")
    #     print(first_event)

    # print("Simulation counters:", state.counters)

    print("\n" + "=" * 60)
    print("RUNNING BUSINESS RULE VALIDATION")
    print("=" * 60)

    business_validator = BusinessRuleValidator(state)
    business_result = business_validator.validate_all()

    print(business_result)
    
    print("\n" + "=" * 60)
    print("RUNNING STATISTICAL QUALITY VALIDATION")
    print("=" * 60)

    statistical_validator = StatisticalQualityValidator(state)
    statistical_result = statistical_validator.validate_all()

    print(statistical_result)

    # print("\nPURCHASE EVENT SAMPLE:")

    # purchase_event = next(
    #     (
    #         event
    #         for event in state.events.values()
    #         if event.get("event_type") == "purchase"
    #     ),
    #     None
    # )

    # print(purchase_event)

    print("\n" + "=" * 60)
    print("RUNNING CROSS-TABLE VALIDATION")
    print("=" * 60)

    cross_table_validator = CrossTableValidator()

    cross_table_result = cross_table_validator.validate_all(
        customers=state.customers,
        orders=state.orders,
        events=state.events,
        daily_metrics=state.daily_metrics,
        counters=state.counters
    )

    print(cross_table_result)

    print("\n" + "=" * 60)
    print("RUNNING DAILY ANALYTICS")
    print("=" * 60)

    daily_analytics = DailyAnalytics(state)

    analytics_result = daily_analytics.calculate()

    for day in analytics_result:
        print(day)

    print("\nDaily analytics reconciliation:")

    analytics_validation = daily_analytics.validate(
        analytics_result
    )

    print(analytics_validation)

    print("\n" + "=" * 60)
    print("BUILDING DATASET QUALITY REPORT")
    print("=" * 60)

    quality_report_builder = DatasetQualityReport(
        dataset_quality_result=quality_result,
        business_rule_result=business_result,
        statistical_result=statistical_result,
        analytics_validation=analytics_validation,
        daily_analytics=analytics_result
    )

    quality_report = quality_report_builder.build()

    print(quality_report)

    print("\n" + "=" * 60)
    print("DATASET QUALITY SUMMARY")
    print("=" * 60)

    quality_summary = quality_report_builder.build_summary()

    print(quality_summary)

    print("\n" + "=" * 60)
    print("RUNNING MULTI-DAY ANALYTICS")
    print("=" * 60)

    multi_day_analytics = MultiDayAnalytics(
        analytics_result
    )

    period_summary = (
        multi_day_analytics.calculate_period_summary()
    )

    print(period_summary)

    daily_trends = (
        multi_day_analytics.calculate_daily_trends()
    )

    print("\nDaily trend metrics:")
    print(daily_trends)

    stability_metrics = (
        multi_day_analytics.calculate_stability_metrics()
    )

    print("\nStability metrics:")
    print(stability_metrics)

    # ============================================================
    # FINAL PHASE 5 VALIDATION
    # ============================================================

    print("\n" + "=" * 60)
    print("FINAL PHASE 5 VALIDATION")
    print("=" * 60)

    # ------------------------------------------------------------
    # SIMULATION PERIOD
    # ------------------------------------------------------------

    assert state.current_day == 30, (
        "Phase 5 validation requires a completed 30-day simulation."
    )

    assert len(state.daily_metrics) == 30, (
        "Expected exactly 30 daily metric records."
    )

    assert len(analytics_result) == 30, (
        "Expected exactly 30 daily analytics records."
    )

    # ------------------------------------------------------------
    # DATASET QUALITY
    # ------------------------------------------------------------

    assert quality_result["passed"], (
        "Dataset quality validation failed."
    )

    # ------------------------------------------------------------
    # BUSINESS RULES
    # ------------------------------------------------------------

    assert business_result["passed"], (
        "Business rule validation failed."
    )

    # ------------------------------------------------------------
    # STATISTICAL QUALITY
    # ------------------------------------------------------------

    assert statistical_result["passed"], (
        "Statistical quality validation failed."
    )

    # Warnings are allowed.
    assert statistical_result["error_count"] == 0, (
        "Statistical validation contains errors."
    )

    # ------------------------------------------------------------
    # ANALYTICS RECONCILIATION
    # ------------------------------------------------------------

    assert analytics_validation["passed"], (
        "Daily analytics reconciliation failed."
    )

    # ------------------------------------------------------------
    # CONSOLIDATED QUALITY REPORT
    # ------------------------------------------------------------

    assert quality_report["passed"], (
        "Consolidated dataset quality report failed."
    )

    assert quality_summary["status"] == "PASS", (
        "Dataset quality summary did not return PASS."
    )

    # ------------------------------------------------------------
    # MULTI-DAY ANALYTICS
    # ------------------------------------------------------------

    assert period_summary["simulation_days"] == 30, (
        "Multi-day analytics does not contain 30 days."
    )

    assert period_summary["total_orders"] == len(state.orders), (
        "Multi-day order total does not match simulation state."
    )

    assert period_summary["total_events"] == len(state.events), (
        "Multi-day event total does not match simulation state."
    )

    state_revenue = sum(
        order.get("gross_amount", 0)
        for order in state.orders.values()
    )

    assert abs(
        period_summary["total_revenue"] - state_revenue
    ) <= 0.01, (
        "Multi-day revenue does not match simulation state."
    )

    # ------------------------------------------------------------
    # GLOBAL COUNTERS
    # ------------------------------------------------------------

    assert state.counters["customer"] == len(state.customers), (
        "Customer counter does not match customer records."
    )

    assert state.counters["order"] == len(state.orders), (
        "Order counter does not match order records."
    )

    assert state.counters["event"] == len(state.events), (
        "Event counter does not match event records."
    )

    print("FINAL PHASE 5 VALIDATION PASSED.")

    print("\n" + "=" * 60) 
    print("EXPORTING SIMULATION DATA")
    print("=" * 60)

    dataset_writer = DatasetWriter()
    dataset_writer.create_run_directory()

    scenario_path = (
        dataset_writer.run_directory
        / "simulation_scenario.json"
    )

    with scenario_path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            config["scenario"],
            file,
            indent=4,
            ensure_ascii=False
        )

    export_result = dataset_writer.export_simulation_state(
        state
    )

    print("\n" + "=" * 60)
    print("RUNTIME DATASET SCHEMA INSPECTION")
    print("=" * 60)

    datasets_to_inspect = {
        "daily_metrics": state.daily_metrics,
        "behavior_history": state.behavior_history,
        "conversion_history": state.conversion_history
    }

    for dataset_name, records in datasets_to_inspect.items():

        print(f"\n{dataset_name.upper()}")

        if not records:
            print("No records")
            continue

        sample = records[0]

        print("Sample:")
        print(sample)

        print("\nFields and Python types:")

        for key, value in sample.items():
            print(
                f"  {key}: "
                f"{type(value).__name__}"
            )

    print("\n" + "=" * 60)
    print("RUNNING RUNTIME SCHEMA VALIDATION")
    print("=" * 60)

    schema_validator = (
        SimulationDatasetSchemaValidator()
    )

    schema_validation_result = (
        schema_validator.validate_state(state)
    )

    print(schema_validation_result)

    assert schema_validation_result["passed"], (
        schema_validation_result["errors"]
    )

    print(
        "RUNTIME SCHEMA VALIDATION PASSED."
    )

    print("\n" + "=" * 60)
    print("RUNNING CATEGORICAL VALUE VALIDATION")
    print("=" * 60)

    categorical_validator = CategoricalValueValidator(
        config=config,
        state=state
    )

    categorical_result = (
        categorical_validator.validate_all()
    )

    print(categorical_result)

    assert categorical_result["passed"], (
        categorical_result["errors"]
    )

    print(
        "CATEGORICAL VALUE VALIDATION PASSED."
    )

    print("\n" + "=" * 60)
    print("BUSINESS KPI ANALYTICS")
    print("=" * 60)

    business_kpi_analytics = BusinessKPIAnalytics(
        state=state
    )

    business_kpis = (
        business_kpi_analytics.calculate_all()
    )

    for section, metrics in business_kpis.items():

        print(f"\n{section.upper()}")

        for metric_name, value in metrics.items():
            print(
                f"{metric_name}: {value}"
            )

    print("\n" + "=" * 60)
    print("PRODUCT ANALYTICS")
    print("=" * 60)

    product_analytics = ProductAnalytics(
        state=state,
        config=config
    )

    product_result = (
        product_analytics.calculate_all()
    )

    print("\nSUMMARY")

    for metric_name, value in (
        product_result["summary"].items()
    ):
        print(
            f"{metric_name}: {value}"
        )

    print("\nCATEGORY PERFORMANCE")

    for category, metrics in (
        product_result[
            "category_performance"
        ].items()
    ):

        print(f"\n{category}")

        for metric_name, value in metrics.items():
            print(
                f"  {metric_name}: {value}"
            )

    print("\n" + "=" * 60)
    print("RETENTION / REPEAT PURCHASE ANALYTICS")
    print("=" * 60)

    retention_analytics = RetentionAnalytics(
        state=state
    )

    retention_result = (
        retention_analytics.calculate_all()
    )

    print("\nSUMMARY")

    for metric_name, value in (
        retention_result["summary"].items()
    ):
        print(
            f"{metric_name}: {value}"
        )

    print("\n" + "=" * 60)
    print("FUNNEL ANALYTICS")
    print("=" * 60)

    funnel_analytics = FunnelAnalytics(
        state=state
    )

    funnel_result = (
        funnel_analytics.calculate_funnel_metrics()
    )

    for section, metrics in funnel_result.items():

        print(f"\n{section.upper()}")

        for metric_name, value in metrics.items():

            print(
                f"{metric_name}: {value}"
            )


    funnel_validation = (
        funnel_analytics.validate()
    )

    print("\nFUNNEL RECONCILIATION")

    for metric_name, value in (
        funnel_validation.items()
    ):
        print(
            f"{metric_name}: {value}"
        )

    assert (
        funnel_validation[
            "purchase_order_match"
        ]
    )

    print(
        "FUNNEL ANALYTICS VALIDATION PASSED."
    )

    print("\n" + "=" * 60)
    print("WEEKLY / MONTHLY ANALYTICS")
    print("=" * 60)

    period_analytics = PeriodAnalytics(
        daily_analytics=analytics_result
    )

    weekly_analytics = (
        period_analytics.calculate_weekly()
    )

    monthly_analytics = (
        period_analytics.calculate_monthly()
    )

    print("\nWEEKLY")

    for row in weekly_analytics:
        print(row)

    print("\nMONTHLY")
    print(monthly_analytics)

    period_validation = (
        period_analytics.validate(
            weekly=weekly_analytics,
            monthly=monthly_analytics
        )
    )

    print("\nPERIOD RECONCILIATION")
    print(period_validation)

    assert all(
        period_validation.values()
    )

    print(
        "WEEKLY / MONTHLY ANALYTICS VALIDATION PASSED."
    )

    print("\n" + "=" * 60)
    print("BUILDING ANALYTICS-READY TABLES")
    print("=" * 60)

    analytics_table_builder = (
        AnalyticsTableBuilder(
            state=state,
            config=config,
            business_kpis=business_kpis,
            product_result=product_result,
            retention_result=retention_result,
            funnel_result=funnel_result,
            daily_analytics=analytics_result,
            weekly_analytics=weekly_analytics,
            monthly_analytics=monthly_analytics
        )
    )

    analytics_tables = (
        analytics_table_builder.build_all()
    )

    for table_name, rows in (
        analytics_tables.items()
    ):

        print(
            f"{table_name}: "
            f"{len(rows)} rows"
        )

    print("\n" + "=" * 60)
    print("EXPORTING BI-FRIENDLY ANALYTICS")
    print("=" * 60)

    analytics_writer = AnalyticsDatasetWriter(
        run_directory=export_result[
            "run_directory"
        ]
    )

    analytics_export_result = (
        analytics_writer.export(
            analytics_tables
        )
    )

    print(
        "Analytics directory:",
        analytics_export_result[
            "analytics_directory"
        ]
    )

    for table_name, summary in (
        analytics_export_result[
            "tables"
        ].items()
    ):

        print(
            f"{table_name}: "
            f"{summary['record_count']} rows"
        )

    print(
        "Analytics manifest:",
        analytics_export_result[
            "manifest"
        ]
    )    

    print("\n" + "=" * 60)
    print("FINAL ANALYTICS DATASET VALIDATION")
    print("=" * 60)

    analytics_dataset_validator = (
        AnalyticsDatasetValidator(
            state=state,
            config=config,
            analytics_tables=analytics_tables,
            analytics_export_result=
                analytics_export_result
        )
    )

    analytics_dataset_validation = (
        analytics_dataset_validator.validate_all()
    )

    print(
        analytics_dataset_validation
    )

    assert (
        analytics_dataset_validation[
            "passed"
        ]
    ), analytics_dataset_validation["errors"]

    print(
        "FINAL ANALYTICS DATASET VALIDATION PASSED."
    )

    print(f"Run ID: {export_result['run_id']}")
    print(f"Output directory: {export_result['run_directory']}")

    for dataset_name, summary in export_result["datasets"].items():
        print(
            f"{dataset_name}: "
            f"{summary['record_count']} records"
        )

    print(f"Manifest: {export_result['manifest']}")