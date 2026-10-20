
-- =====================================================
-- PHASE 8.5.5.1 - POSTGRESQL INGESTION VALIDATION
-- =====================================================

\pset pager off
\set run_id 'simulation_run_20261004_120957'

BEGIN;

-- ==========================================
-- 1. TABLE COUNTS AND INGESTION REGISTRY
-- ==========================================

CREATE TEMP TABLE staging_count_audit
ON COMMIT DROP AS

WITH expected(dataset, expected_rows) AS (
    VALUES
        ('customers', 10000::BIGINT),
        ('product_master', 29::BIGINT),
        ('orders', 2913::BIGINT),
        ('events', 96508::BIGINT),
        ('behavior_history', 93595::BIGINT),
        ('conversion_history', 53833::BIGINT),
        ('daily_metrics_source', 90::BIGINT),
        ('daily_metrics_cleaned', 90::BIGINT)
),

actual(dataset, actual_rows) AS (
    SELECT 'customers', COUNT(*)
    FROM staging.customers
    WHERE run_id = :'run_id'

    UNION ALL
    SELECT 'product_master', COUNT(*)
    FROM staging.product_master
    WHERE run_id = :'run_id'

    UNION ALL
    SELECT 'orders', COUNT(*)
    FROM staging.orders
    WHERE run_id = :'run_id'

    UNION ALL
    SELECT 'events', COUNT(*)
    FROM staging.events
    WHERE run_id = :'run_id'

    UNION ALL
    SELECT 'behavior_history', COUNT(*)
    FROM staging.behavior_history
    WHERE run_id = :'run_id'

    UNION ALL
    SELECT 'conversion_history', COUNT(*)
    FROM staging.conversion_history
    WHERE run_id = :'run_id'

    UNION ALL
    SELECT 'daily_metrics_source', COUNT(*)
    FROM staging.daily_metrics_source
    WHERE run_id = :'run_id'

    UNION ALL
    SELECT 'daily_metrics_cleaned', COUNT(*)
    FROM staging.daily_metrics_cleaned
    WHERE run_id = :'run_id'
)

SELECT
    e.dataset,
    e.expected_rows,
    a.actual_rows,
    r.loaded_rows AS registry_rows,

    CASE
        WHEN a.actual_rows = e.expected_rows
         AND r.loaded_rows = e.expected_rows
         AND r.expected_rows = e.expected_rows
         AND r.source_sha256 ~ '^[0-9a-f]{64}$'
        THEN 'PASS'
        ELSE 'FAIL'
    END AS status

FROM expected e
JOIN actual a USING (dataset)

LEFT JOIN staging.ingestion_registry r
    ON r.dataset_name = e.dataset
   AND r.run_id = :'run_id';


SELECT *
FROM staging_count_audit
ORDER BY dataset;


-- ==========================================
-- 2. BUSINESS METRICS RECONCILIATION
-- ==========================================

CREATE TEMP TABLE staging_metrics_audit
ON COMMIT DROP AS

WITH measures AS (
    SELECT
        (SELECT COALESCE(SUM(gross_amount), 0)
         FROM staging.orders
         WHERE run_id = :'run_id') AS order_revenue,

        (SELECT COALESCE(SUM(lifetime_spend), 0)
         FROM staging.customers
         WHERE run_id = :'run_id') AS customer_revenue,

        (SELECT COALESCE(SUM(lifetime_orders), 0)
         FROM staging.customers
         WHERE run_id = :'run_id') AS customer_orders,

        (SELECT COUNT(*)
         FROM staging.events
         WHERE run_id = :'run_id'
           AND event_type = 'purchase') AS purchases,

        (SELECT COUNT(*)
         FROM staging.conversion_history
         WHERE run_id = :'run_id'
           AND result_json->>'converted' = 'true')
            AS historical_conversions,

        (SELECT COALESCE(SUM(clean_order_count), 0)
         FROM staging.daily_metrics_cleaned
         WHERE run_id = :'run_id') AS daily_orders,

        (SELECT COALESCE(SUM(clean_event_count), 0)
         FROM staging.daily_metrics_cleaned
         WHERE run_id = :'run_id') AS daily_events,

        (SELECT COALESCE(
            SUM(behavior_event_count), 0)
         FROM staging.daily_metrics_cleaned
         WHERE run_id = :'run_id') AS daily_behaviors,

        (SELECT COALESCE(
            SUM(conversion_decisions_evaluated), 0)
         FROM staging.daily_metrics_cleaned
         WHERE run_id = :'run_id') AS daily_decisions,

        (SELECT COUNT(*)
         FROM staging.ingestion_registry
         WHERE run_id = :'run_id') AS registry_entries
)

SELECT
    v.metric,
    v.actual,
    v.expected,

    CASE
        WHEN v.actual = v.expected
        THEN 'PASS'
        ELSE 'FAIL'
    END AS status

FROM measures m

CROSS JOIN LATERAL (
    VALUES
        ('order_revenue_inr',
         m.order_revenue, 53812160::NUMERIC),

        ('customer_revenue_inr',
         m.customer_revenue, 53812160::NUMERIC),

        ('customer_lifetime_orders',
         m.customer_orders, 2913::NUMERIC),

        ('purchase_events',
         m.purchases, 2913::NUMERIC),

        ('historical_conversions',
         m.historical_conversions, 2915::NUMERIC),

        ('daily_clean_orders',
         m.daily_orders, 2913::NUMERIC),

        ('daily_clean_events',
         m.daily_events, 96508::NUMERIC),

        ('daily_behavior_events',
         m.daily_behaviors, 93595::NUMERIC),

        ('daily_conversion_decisions',
         m.daily_decisions, 53833::NUMERIC),

        ('ingestion_registry_entries',
         m.registry_entries, 8::NUMERIC)
) AS v(metric, actual, expected);


SELECT *
FROM staging_metrics_audit
ORDER BY metric;


-- ==========================================
-- 3. FAIL IF ANY CHECK DOES NOT PASS
-- ==========================================

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM staging_count_audit
        WHERE status <> 'PASS'
    ) THEN
        RAISE EXCEPTION
            'Staging table count/registry validation failed';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM staging_metrics_audit
        WHERE status <> 'PASS'
    ) THEN
        RAISE EXCEPTION
            'Staging business metric validation failed';
    END IF;

    RAISE NOTICE
        'POSTGRESQL INGESTION COUNTS AUDIT PASSED.';
END
$$;

COMMIT;
