import argparse
import json
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
from validation.dataset_quality_validator import (
    DatasetQualityValidator
)
from validation.business_rule_validator import (
    BusinessRuleValidator
)
from validation.statistical_quality_validator import (
    StatisticalQualityValidator
)
from validation.cross_table_validator import (
    CrossTableValidator
)
from validation.schema_validator import (
    SimulationDatasetSchemaValidator
)
from validation.categorical_value_validator import (
    CategoricalValueValidator
)
from validation.analytics_dataset_validator import (
    AnalyticsDatasetValidator
)

from analytics.daily_analytics import DailyAnalytics
from analytics.multi_day_analytics import MultiDayAnalytics
from analytics.business_kpis import BusinessKPIAnalytics
from analytics.product_analytics import ProductAnalytics
from analytics.retention_analytics import RetentionAnalytics
from analytics.funnel_analytics import FunnelAnalytics
from analytics.period_analytics import PeriodAnalytics
from analytics.analytics_tables import AnalyticsTableBuilder

from exporters.dataset_writer import DatasetWriter
from exporters.analytics_writer import AnalyticsDatasetWriter


def run_production_dataset(
    days=90,
    customer_count=10000,
    scenario_name="baseline"
):

    print("=" * 65)
    print("FINAL PRODUCTION DATASET GENERATION")
    print("=" * 65)

    print(f"Scenario: {scenario_name}")
    print(f"Simulation days: {days}")
    print(f"Customers: {customer_count}")

    # ======================================================
    # CONFIG
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

    print("\n[1] Generating customer population...")

    customer_engine.generate_customer_population(
        count=customer_count,
        start_id=1,
        current_day=1
    )

    assert (
        len(state.customers)
        == customer_count
    )

    # ======================================================
    # 90-DAY SIMULATION
    # ======================================================

    print("[2] Running production simulation...")

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

    _, peak_memory = (
        tracemalloc.get_traced_memory()
    )

    tracemalloc.stop()

    # ======================================================
    # BASIC SIMULATION VALIDATION
    # ======================================================

    print("[3] Validating simulation durability...")

    assert state.current_day == days
    assert len(results) == days
    assert len(state.daily_metrics) == days

    assert (
        state.counters["customer"]
        == len(state.customers)
    )

    assert (
        state.counters["order"]
        == len(state.orders)
    )

    assert (
        state.counters["event"]
        == len(state.events)
    )

    purchase_events = sum(
        1
        for event
        in state.events.values()
        if event.get("event_type")
        == "purchase"
    )

    assert (
        purchase_events
        == len(state.orders)
    )

    # ======================================================
    # DATASET QUALITY
    # ======================================================

    print("[4] Running dataset quality validation...")

    dataset_quality_result = (
        DatasetQualityValidator(
            state
        ).validate_all()
    )

    assert dataset_quality_result[
        "passed"
    ], dataset_quality_result["errors"]

    # ======================================================
    # BUSINESS RULES
    # ======================================================

    print("[5] Running business-rule validation...")

    business_rule_result = (
        BusinessRuleValidator(
            state
        ).validate_all()
    )

    assert business_rule_result[
        "passed"
    ], business_rule_result["errors"]

    # ======================================================
    # STATISTICAL QUALITY
    # ======================================================

    print("[6] Running statistical validation...")

    statistical_result = (
        StatisticalQualityValidator(
            state
        ).validate_all()
    )

    assert statistical_result[
        "passed"
    ], statistical_result["errors"]

    # ======================================================
    # CROSS-TABLE VALIDATION
    # ======================================================

    print("[7] Running cross-table validation...")

    cross_table_result = (
        CrossTableValidator()
        .validate_all(
            customers=state.customers,
            orders=state.orders,
            events=state.events,
            daily_metrics=state.daily_metrics,
            counters=state.counters
        )
    )

    assert cross_table_result[
        "passed"
    ], cross_table_result["errors"]

    # ======================================================
    # RUNTIME SCHEMA
    # ======================================================

    print("[8] Running runtime schema validation...")

    schema_result = (
        SimulationDatasetSchemaValidator()
        .validate_state(
            state
        )
    )

    assert schema_result[
        "passed"
    ], schema_result["errors"]

    # ======================================================
    # CATEGORICAL VALUES
    # ======================================================

    print("[9] Running categorical validation...")

    categorical_result = (
        CategoricalValueValidator(
            config=config,
            state=state
        ).validate_all()
    )

    assert categorical_result[
        "passed"
    ], categorical_result["errors"]

    # ======================================================
    # DAILY ANALYTICS
    # ======================================================

    print("[10] Building daily analytics...")

    daily_analytics_engine = (
        DailyAnalytics(
            state
        )
    )

    daily_analytics = (
        daily_analytics_engine.calculate()
    )

    daily_validation = (
        daily_analytics_engine.validate(
            daily_analytics
        )
    )

    assert daily_validation[
        "passed"
    ], daily_validation["errors"]

    assert (
        len(daily_analytics)
        == days
    )

    # ======================================================
    # MULTI-DAY ANALYTICS
    # ======================================================

    print("[11] Building multi-day analytics...")

    multi_day_analytics = (
        MultiDayAnalytics(
            daily_analytics
        )
    )

    period_summary = (
        multi_day_analytics
        .calculate_period_summary()
    )

    assert (
        period_summary[
            "simulation_days"
        ]
        == days
    )

    assert (
        period_summary[
            "total_orders"
        ]
        == len(state.orders)
    )

    assert (
        period_summary[
            "total_events"
        ]
        == len(state.events)
    )

    # ======================================================
    # BUSINESS KPI ANALYTICS
    # ======================================================

    print("[12] Building business KPIs...")

    business_kpis = (
        BusinessKPIAnalytics(
            state=state
        ).calculate_all()
    )

    # ======================================================
    # PRODUCT ANALYTICS
    # ======================================================

    print("[13] Building product analytics...")

    product_result = (
        ProductAnalytics(
            state=state,
            config=config
        ).calculate_all()
    )

    # ======================================================
    # RETENTION ANALYTICS
    # ======================================================

    print("[14] Building retention analytics...")

    retention_result = (
        RetentionAnalytics(
            state=state
        ).calculate_all()
    )

    # ======================================================
    # FUNNEL ANALYTICS
    # ======================================================

    print("[15] Building funnel analytics...")

    funnel_engine = FunnelAnalytics(
        state=state
    )

    funnel_result = (
        funnel_engine
        .calculate_funnel_metrics()
    )

    funnel_validation = (
        funnel_engine.validate()
    )

    assert (
        funnel_validation[
            "purchase_order_match"
        ]
    )

    # ======================================================
    # PERIOD ANALYTICS
    # ======================================================

    print("[16] Building weekly/monthly analytics...")

    period_analytics = PeriodAnalytics(
        daily_analytics=daily_analytics
    )

    weekly_analytics = (
        period_analytics
        .calculate_weekly()
    )

    monthly_analytics = (
        period_analytics
        .calculate_monthly()
    )

    period_validation = (
        period_analytics.validate(
            weekly=weekly_analytics,
            monthly=monthly_analytics
        )
    )

    assert all(
        period_validation.values()
    )

    # ======================================================
    # ANALYTICS-READY TABLES
    # ======================================================

    print("[17] Building analytics-ready tables...")

    analytics_tables = (
        AnalyticsTableBuilder(
            state=state,
            config=config,
            business_kpis=business_kpis,
            product_result=product_result,
            retention_result=retention_result,
            funnel_result=funnel_result,
            daily_analytics=daily_analytics,
            weekly_analytics=weekly_analytics,
            monthly_analytics=monthly_analytics
        ).build_all()
    )

    # ======================================================
    # RAW DATA EXPORT
    # ======================================================

    print("[18] Exporting runtime datasets...")

    dataset_writer = DatasetWriter()

    dataset_writer.create_run_directory()

    # Save scenario before export.
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

    export_result = (
        dataset_writer
        .export_simulation_state(
            state
        )
    )

    # ======================================================
    # ANALYTICS EXPORT
    # ======================================================

    print("[19] Exporting analytics datasets...")

    analytics_writer = (
        AnalyticsDatasetWriter(
            run_directory=
                export_result[
                    "run_directory"
                ]
        )
    )

    analytics_export_result = (
        analytics_writer.export(
            analytics_tables
        )
    )

    # ======================================================
    # FINAL ANALYTICS VALIDATION
    # ======================================================

    print("[20] Running final analytics validation...")

    analytics_validation_result = (
        AnalyticsDatasetValidator(
            state=state,
            config=config,
            analytics_tables=
                analytics_tables,
            analytics_export_result=
                analytics_export_result
        ).validate_all()
    )

    assert (
        analytics_validation_result[
            "passed"
        ]
    ), analytics_validation_result[
        "errors"
    ]

    # ======================================================
    # FINAL PRODUCTION FREEZE MANIFEST
    # ======================================================

    total_revenue = round(
        sum(
            order.get(
                "gross_amount",
                0
            )
            for order
            in state.orders.values()
        ),
        2
    )

    freeze_manifest = {
        "dataset_status":
            "FROZEN",

        "purpose":
            "M14 Project 1 synthetic enterprise dataset",

        "scenario":
            scenario_name,

        "simulation_days":
            days,

        "customer_count":
            len(state.customers),

        "order_count":
            len(state.orders),

        "event_count":
            len(state.events),

        "behavior_history_count":
            len(
                state.behavior_history
            ),

        "conversion_history_count":
            len(
                state.conversion_history
            ),

        "daily_metrics_count":
            len(
                state.daily_metrics
            ),

        "purchase_event_count":
            purchase_events,

        "total_revenue":
            total_revenue,

        "elapsed_seconds":
            round(
                elapsed_seconds,
                4
            ),

        "peak_python_memory_mb":
            round(
                peak_memory
                / (1024 * 1024),
                2
            ),

        "validations": {
            "dataset_quality":
                dataset_quality_result[
                    "passed"
                ],

            "business_rules":
                business_rule_result[
                    "passed"
                ],

            "statistical_quality":
                statistical_result[
                    "passed"
                ],

            "cross_table":
                cross_table_result[
                    "passed"
                ],

            "runtime_schema":
                schema_result[
                    "passed"
                ],

            "categorical_values":
                categorical_result[
                    "passed"
                ],

            "daily_analytics":
                daily_validation[
                    "passed"
                ],

            "analytics_dataset":
                analytics_validation_result[
                    "passed"
                ]
        }
    }

    freeze_path = (
        export_result[
            "run_directory"
        ]
        / "dataset_freeze_manifest.json"
    )

    with freeze_path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            freeze_manifest,
            file,
            indent=4,
            ensure_ascii=False
        )

    # ======================================================
    # FINAL SUMMARY
    # ======================================================

    print("\n" + "=" * 65)
    print("FINAL DATASET GENERATION COMPLETE")
    print("=" * 65)

    print(
        f"Run ID: "
        f"{export_result['run_id']}"
    )

    print(
        f"Output directory: "
        f"{export_result['run_directory']}"
    )

    print(
        f"Scenario: "
        f"{scenario_name}"
    )

    print(
        f"Simulation days: "
        f"{days}"
    )

    print(
        f"Customers: "
        f"{len(state.customers)}"
    )

    print(
        f"Orders: "
        f"{len(state.orders)}"
    )

    print(
        f"Events: "
        f"{len(state.events)}"
    )

    print(
        f"Behavior history: "
        f"{len(state.behavior_history)}"
    )

    print(
        f"Conversion history: "
        f"{len(state.conversion_history)}"
    )

    print(
        f"Daily metrics: "
        f"{len(state.daily_metrics)}"
    )

    print(
        f"Revenue: "
        f"{total_revenue:.2f}"
    )

    print(
        f"Elapsed seconds: "
        f"{elapsed_seconds:.4f}"
    )

    print(
        f"Peak Python memory: "
        f"{peak_memory / (1024 * 1024):.2f} MB"
    )

    print(
        f"Raw manifest: "
        f"{export_result['manifest']}"
    )

    print(
        f"Analytics manifest: "
        f"{analytics_export_result['manifest']}"
    )

    print(
        f"Freeze manifest: "
        f"{freeze_path}"
    )

    print(
        "\nALL PRODUCTION VALIDATIONS PASSED."
    )

    print(
        "FINAL 90-DAY DATASET FROZEN."
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
        default=10000
    )

    parser.add_argument(
        "--scenario",
        default="baseline"
    )

    args = parser.parse_args()

    run_production_dataset(
        days=args.days,
        customer_count=args.customers,
        scenario_name=args.scenario
    )