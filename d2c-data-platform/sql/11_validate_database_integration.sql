
-- =====================================================
-- PHASE 8.10.2A - DATABASE INTEGRATION VALIDATION
-- =====================================================

\set ON_ERROR_STOP on
\pset pager off

\echo
\echo =====================================================
\echo PHASE 8 - END-TO-END DATABASE INTEGRATION
\echo =====================================================

-- Reuse our existing, verified SQL audits.

\echo
\echo [1/4] STAGING INGESTION VALIDATION
\ir 02_validate_ingestion.sql

\echo
\echo [2/4] REFERENTIAL INTEGRITY VALIDATION
\ir 03_validate_referential_integrity.sql

\echo
\echo [3/4] WAREHOUSE RECONCILIATION
\ir 10_validate_warehouse.sql


-- =====================================================
-- 4. DIRECT CROSS-LAYER RECONCILIATION
-- =====================================================

\echo
\echo [4/4] CROSS-LAYER RECONCILIATION

\set run_id 'simulation_run_20261004_120957'

BEGIN;

CREATE TEMP TABLE e2e_row_audit
ON COMMIT DROP AS

SELECT *
FROM (
    VALUES

    (
        'customers',
        10000::BIGINT,
        (SELECT COUNT(*)
         FROM staging.customers
         WHERE run_id = :'run_id'),
        (SELECT COUNT(*)
         FROM warehouse.dim_customers
         WHERE run_id = :'run_id')
    ),

    (
        'products',
        29::BIGINT,
        (SELECT COUNT(*)
         FROM staging.product_master
         WHERE run_id = :'run_id'),
        (SELECT COUNT(*)
         FROM warehouse.dim_products
         WHERE run_id = :'run_id')
    ),

    (
        'simulation_days',
        90::BIGINT,
        (SELECT COUNT(*)
         FROM staging.daily_metrics_cleaned
         WHERE run_id = :'run_id'),
        (SELECT COUNT(*)
         FROM warehouse.dim_days
         WHERE run_id = :'run_id')
    ),

    (
        'orders',
        2913::BIGINT,
        (SELECT COUNT(*)
         FROM staging.orders
         WHERE run_id = :'run_id'),
        (SELECT COUNT(*)
         FROM warehouse.fact_orders
         WHERE run_id = :'run_id')
    ),

    (
        'events',
        96508::BIGINT,
        (SELECT COUNT(*)
         FROM staging.events
         WHERE run_id = :'run_id'),
        (SELECT COUNT(*)
         FROM warehouse.fact_events
         WHERE run_id = :'run_id')
    ),

    (
        'behavior_events',
        93595::BIGINT,
        (SELECT COUNT(*)
         FROM staging.behavior_history
         WHERE run_id = :'run_id'),
        (SELECT COUNT(*)
         FROM warehouse.fact_events
         WHERE run_id = :'run_id'
           AND event_type <> 'purchase')
    ),

    (
        'purchase_events',
        2913::BIGINT,
        (SELECT COUNT(*)
         FROM staging.events
         WHERE run_id = :'run_id'
           AND event_type = 'purchase'),
        (SELECT COUNT(*)
         FROM warehouse.fact_events
         WHERE run_id = :'run_id'
           AND event_type = 'purchase')
    ),

    (
        'conversion_evaluations',
        53833::BIGINT,
        (SELECT COUNT(*)
         FROM staging.conversion_history
         WHERE run_id = :'run_id'),
        (SELECT COALESCE(
             SUM(conversion_decisions_evaluated), 0)
         FROM warehouse.fact_daily_metrics
         WHERE run_id = :'run_id')
    ),

    (
        'historical_conversions',
        2915::BIGINT,
        (SELECT COUNT(*)
         FROM staging.conversion_history
         WHERE run_id = :'run_id'
           AND result_json->>'converted' = 'true'),
        (SELECT COALESCE(
             SUM(historical_converted_decisions), 0)
         FROM warehouse.fact_daily_metrics
         WHERE run_id = :'run_id')
    )

) AS checks(
    check_name,
    expected_rows,
    staging_rows,
    warehouse_rows
);


SELECT
    check_name,
    expected_rows,
    staging_rows,
    warehouse_rows,

    CASE
        WHEN expected_rows = staging_rows
         AND staging_rows = warehouse_rows
        THEN 'PASS'
        ELSE 'FAIL'
    END AS status

FROM e2e_row_audit
ORDER BY check_name;


-- =====================================================
-- CROSS-LAYER REVENUE VALIDATION
-- =====================================================

CREATE TEMP TABLE e2e_revenue_audit
ON COMMIT DROP AS

SELECT *
FROM (
    VALUES

    (
        'staging_orders',
        (SELECT COALESCE(
            SUM(gross_amount), 0)
         FROM staging.orders
         WHERE run_id = :'run_id')
    ),

    (
        'warehouse_orders',
        (SELECT COALESCE(
            SUM(gross_amount), 0)
         FROM warehouse.fact_orders
         WHERE run_id = :'run_id')
    ),

    (
        'warehouse_daily_metrics',
        (SELECT COALESCE(
            SUM(gross_revenue), 0)
         FROM warehouse.fact_daily_metrics
         WHERE run_id = :'run_id')
    ),

    (
        'warehouse_customers',
        (SELECT COALESCE(
            SUM(lifetime_spend), 0)
         FROM warehouse.dim_customers
         WHERE run_id = :'run_id')
    )

) AS checks(source_name, revenue_inr);


SELECT
    source_name,
    revenue_inr,

    CASE
        WHEN revenue_inr = 53812160.00
        THEN 'PASS'
        ELSE 'FAIL'
    END AS status

FROM e2e_revenue_audit
ORDER BY source_name;


-- =====================================================
-- FINAL AUTOMATED ASSERTIONS
-- =====================================================

DO $$
DECLARE
    v_run TEXT := 'simulation_run_20261004_120957';
    v_registry BIGINT;
BEGIN

    IF (
        SELECT COUNT(*) FROM e2e_row_audit
    ) <> 9
    OR EXISTS (
        SELECT 1
        FROM e2e_row_audit
        WHERE expected_rows IS DISTINCT FROM staging_rows
           OR staging_rows IS DISTINCT FROM warehouse_rows
    ) THEN

        RAISE EXCEPTION
            'Cross-layer row reconciliation failed';

    END IF;


    IF (
        SELECT COUNT(*) FROM e2e_revenue_audit
    ) <> 4
    OR EXISTS (
        SELECT 1
        FROM e2e_revenue_audit
        WHERE revenue_inr IS DISTINCT FROM 53812160.00
    ) THEN

        RAISE EXCEPTION
            'Cross-layer revenue reconciliation failed';

    END IF;


    SELECT COUNT(*)
    INTO v_registry
    FROM staging.ingestion_registry
    WHERE run_id = v_run;

    IF v_registry <> 8 THEN

        RAISE EXCEPTION
            'Expected 8 ingestion registry entries, found %',
            v_registry;

    END IF;


    RAISE NOTICE 'Cross-layer row checks: 9/9 PASSED';
    RAISE NOTICE 'Cross-layer revenue checks: 4/4 PASSED';
    RAISE NOTICE 'Ingestion registry entries: 8/8';
    RAISE NOTICE
        'END-TO-END DATABASE INTEGRATION VALIDATION PASSED.';

END
$$;

COMMIT;