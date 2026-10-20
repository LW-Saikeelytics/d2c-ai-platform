
-- =====================================================
-- PHASE 8.7.5 - FINAL WAREHOUSE RECONCILIATION
-- =====================================================

\pset pager off
\set run_id 'simulation_run_20261004_120957'

BEGIN;

SELECT set_config(
    'm14.run_id',
    :'run_id',
    true
);


-- =====================================================
-- 1. VALIDATE WAREHOUSE TABLE COUNTS
-- =====================================================

CREATE TEMP TABLE warehouse_count_audit
ON COMMIT DROP AS

SELECT *
FROM (
    VALUES
    (
        'dim_customers',
        10000::BIGINT,
        (SELECT COUNT(*)
         FROM warehouse.dim_customers
         WHERE run_id = :'run_id')
    ),
    (
        'dim_products',
        29::BIGINT,
        (SELECT COUNT(*)
         FROM warehouse.dim_products
         WHERE run_id = :'run_id')
    ),
    (
        'dim_days',
        90::BIGINT,
        (SELECT COUNT(*)
         FROM warehouse.dim_days
         WHERE run_id = :'run_id')
    ),
    (
        'fact_orders',
        2913::BIGINT,
        (SELECT COUNT(*)
         FROM warehouse.fact_orders
         WHERE run_id = :'run_id')
    ),
    (
        'fact_events',
        96508::BIGINT,
        (SELECT COUNT(*)
         FROM warehouse.fact_events
         WHERE run_id = :'run_id')
    ),
    (
        'fact_daily_metrics',
        90::BIGINT,
        (SELECT COUNT(*)
         FROM warehouse.fact_daily_metrics
         WHERE run_id = :'run_id')
    )
) AS checks(table_name, expected_rows, actual_rows);


SELECT
    table_name,
    expected_rows,
    actual_rows,
    CASE
        WHEN expected_rows = actual_rows
        THEN 'PASS'
        ELSE 'FAIL'
    END AS status
FROM warehouse_count_audit
ORDER BY table_name;


-- =====================================================
-- 2. VERIFY DIMENSIONS AGAINST STAGING
-- =====================================================

CREATE TEMP TABLE warehouse_parity_audit
ON COMMIT DROP AS

SELECT
    'customers_match_staging' AS check_name,
    COUNT(*) AS violations

FROM staging.customers s

LEFT JOIN warehouse.dim_customers d
    ON d.run_id = s.run_id
   AND d.customer_id = s.customer_id

WHERE s.run_id = :'run_id'
  AND (
      d.customer_key IS NULL
      OR (to_jsonb(d) - 'customer_key')
         IS DISTINCT FROM to_jsonb(s)
  )

UNION ALL

SELECT
    'products_match_staging',
    COUNT(*)

FROM staging.product_master s

LEFT JOIN warehouse.dim_products d
    ON d.run_id = s.run_id
   AND d.product_id = s.product_id

WHERE s.run_id = :'run_id'
  AND (
      d.product_key IS NULL
      OR (to_jsonb(d) - 'product_key')
         IS DISTINCT FROM to_jsonb(s)
  )

UNION ALL

SELECT
    'days_match_staging',
    COUNT(*)

FROM staging.daily_metrics_cleaned s

LEFT JOIN warehouse.dim_days d
    ON d.run_id = s.run_id
   AND d.simulation_day = s.simulation_day

WHERE s.run_id = :'run_id'
  AND d.day_key IS NULL

UNION ALL

-- Every staged order must match its warehouse
-- order and resolved surrogate dimension keys.

SELECT
    'orders_match_staging',
    COUNT(*)

FROM staging.orders s

LEFT JOIN warehouse.dim_customers c
    ON c.run_id = s.run_id
   AND c.customer_id = s.customer_id

LEFT JOIN warehouse.dim_products p
    ON p.run_id = s.run_id
   AND p.product_id = s.product_id

LEFT JOIN warehouse.dim_days d
    ON d.run_id = s.run_id
   AND d.simulation_day = s.simulation_day

LEFT JOIN warehouse.fact_orders f
    ON f.run_id = s.run_id
   AND f.order_id = s.order_id

WHERE s.run_id = :'run_id'
  AND (
      f.order_id IS NULL

      OR ROW(
          f.day_key,
          f.customer_key,
          f.product_key,
          f.variant_id,
          f.channel,
          f.quantity,
          f.unit_price,
          f.gross_amount
      ) IS DISTINCT FROM ROW(
          d.day_key,
          c.customer_key,
          p.product_key,
          s.variant_id,
          s.channel,
          s.quantity,
          s.unit_price,
          s.gross_amount
      )
  )

UNION ALL

-- Every staged event must match its warehouse
-- event and resolved surrogate dimension keys.

SELECT
    'events_match_staging',
    COUNT(*)

FROM staging.events s

LEFT JOIN warehouse.dim_customers c
    ON c.run_id = s.run_id
   AND c.customer_id = s.customer_id

LEFT JOIN warehouse.dim_products p
    ON p.run_id = s.run_id
   AND p.product_id = s.product_id

LEFT JOIN warehouse.dim_days d
    ON d.run_id = s.run_id
   AND d.simulation_day = s.simulation_day

LEFT JOIN warehouse.fact_events f
    ON f.run_id = s.run_id
   AND f.event_id = s.event_id

WHERE s.run_id = :'run_id'
  AND (
      f.event_id IS NULL

      OR ROW(
          f.day_key,
          f.customer_key,
          f.product_key,
          f.event_type,
          f.order_id
      ) IS DISTINCT FROM ROW(
          d.day_key,
          c.customer_key,
          p.product_key,
          s.event_type,
          s.order_id
      )
  );


SELECT
    check_name,
    violations,
    CASE
        WHEN violations = 0
        THEN 'PASS'
        ELSE 'FAIL'
    END AS status
FROM warehouse_parity_audit
ORDER BY check_name;


-- =====================================================
-- 3. INDEPENDENTLY RECOMPUTE ALL 90 DAYS
-- =====================================================

CREATE TEMP TABLE warehouse_daily_audit
ON COMMIT DROP AS

WITH

days AS (
    SELECT generate_series(1, 90)::BIGINT
        AS simulation_day
),

orders AS (
    SELECT
        d.simulation_day,
        COUNT(*) AS order_count,
        COUNT(DISTINCT f.customer_key)
            AS unique_buyers,
        SUM(f.gross_amount) AS revenue

    FROM warehouse.fact_orders f

    JOIN warehouse.dim_days d
        ON d.run_id = f.run_id
       AND d.day_key = f.day_key

    WHERE f.run_id = :'run_id'
    GROUP BY d.simulation_day
),

events AS (
    SELECT
        d.simulation_day,
        COUNT(*) AS event_count,

        COUNT(*) FILTER (
            WHERE f.event_type = 'purchase'
        ) AS purchase_count,

        COUNT(*) FILTER (
            WHERE f.event_type <> 'purchase'
        ) AS behavior_count

    FROM warehouse.fact_events f

    JOIN warehouse.dim_days d
        ON d.run_id = f.run_id
       AND d.day_key = f.day_key

    WHERE f.run_id = :'run_id'
    GROUP BY d.simulation_day
),

behaviors AS (
    SELECT
        simulation_day,
        COUNT(*) AS behavior_count,
        COUNT(DISTINCT customer_id)
            AS active_customers

    FROM staging.behavior_history
    WHERE run_id = :'run_id'
    GROUP BY simulation_day
),

conversions AS (
    SELECT
        simulation_day,
        COUNT(*) AS evaluated,

        COUNT(*) FILTER (
            WHERE result_json->>'converted' = 'true'
        ) AS converted

    FROM staging.conversion_history
    WHERE run_id = :'run_id'
    GROUP BY simulation_day
)

SELECT
    days.simulation_day,
    COALESCE(o.order_count, 0) AS orders,
    COALESCE(b.behavior_count, 0) AS behaviors,
    COALESCE(e.event_count, 0) AS events,
    COALESCE(v.evaluated, 0) AS decisions,
    COALESCE(o.revenue, 0)::NUMERIC(18,2)
        AS revenue,

    CASE

        WHEN d.day_key IS NULL
          OR f.day_key IS NULL
          OR s.simulation_day IS NULL

          -- Compare cleaned staging daily metrics
          -- with the warehouse daily facts.

          OR ROW(
              f.customers,
              f.behavior_active_customers,
              f.behavior_event_count,
              f.conversion_decisions_evaluated,
              f.historical_converted_decisions,
              f.clean_order_count,
              f.clean_purchase_event_count,
              f.clean_event_count
          ) IS DISTINCT FROM ROW(
              s.customers,
              s.behavior_active_customers,
              s.behavior_event_count,
              s.conversion_decisions_evaluated,
              s.historical_converted_decisions,
              s.clean_order_count,
              s.clean_purchase_event_count,
              s.clean_event_count
          )

          -- Recalculate business measures using
          -- independent order, event, behavior,
          -- and conversion records.

          OR ROW(
              f.purchasing_customers,
              f.behavior_active_customers,
              f.behavior_event_count,
              f.conversion_decisions_evaluated,
              f.historical_converted_decisions,
              f.clean_order_count,
              f.clean_purchase_event_count,
              f.clean_event_count,
              f.gross_revenue
          ) IS DISTINCT FROM ROW(
              COALESCE(o.unique_buyers, 0),
              COALESCE(b.active_customers, 0),
              COALESCE(b.behavior_count, 0),
              COALESCE(v.evaluated, 0),
              COALESCE(v.converted, 0),
              COALESCE(o.order_count, 0),
              COALESCE(e.purchase_count, 0),
              COALESCE(e.event_count, 0),
              COALESCE(o.revenue, 0)
          )

          OR COALESCE(e.behavior_count, 0)
             <> COALESCE(b.behavior_count, 0)

          OR COALESCE(e.purchase_count, 0)
             <> COALESCE(o.order_count, 0)

        THEN 'FAIL'
        ELSE 'PASS'
    END AS status

FROM days

LEFT JOIN warehouse.dim_days d
    ON d.run_id = :'run_id'
   AND d.simulation_day = days.simulation_day

LEFT JOIN warehouse.fact_daily_metrics f
    ON f.run_id = d.run_id
   AND f.day_key = d.day_key

LEFT JOIN staging.daily_metrics_cleaned s
    ON s.run_id = :'run_id'
   AND s.simulation_day = days.simulation_day

LEFT JOIN orders o
    ON o.simulation_day = days.simulation_day

LEFT JOIN events e
    ON e.simulation_day = days.simulation_day

LEFT JOIN behaviors b
    ON b.simulation_day = days.simulation_day

LEFT JOIN conversions v
    ON v.simulation_day = days.simulation_day;


SELECT
    COUNT(*) AS days_checked,
    COUNT(*) FILTER (
        WHERE status = 'PASS'
    ) AS days_passed,
    COUNT(*) FILTER (
        WHERE status = 'FAIL'
    ) AS days_failed
FROM warehouse_daily_audit;


SELECT *
FROM warehouse_daily_audit
WHERE simulation_day = 30;


-- =====================================================
-- 4. CROSS-WAREHOUSE BUSINESS TOTALS
-- =====================================================

CREATE TEMP TABLE warehouse_total_audit
ON COMMIT DROP AS

SELECT *
FROM (
    VALUES
    (
        'orders_revenue_inr',
        (SELECT COALESCE(SUM(gross_amount), 0)
         FROM warehouse.fact_orders
         WHERE run_id = :'run_id'),
        53812160.00::NUMERIC
    ),
    (
        'daily_revenue_inr',
        (SELECT COALESCE(SUM(gross_revenue), 0)
         FROM warehouse.fact_daily_metrics
         WHERE run_id = :'run_id'),
        53812160.00::NUMERIC
    ),
    (
        'customer_revenue_inr',
        (SELECT COALESCE(SUM(lifetime_spend), 0)
         FROM warehouse.dim_customers
         WHERE run_id = :'run_id'),
        53812160.00::NUMERIC
    ),
    (
        'units_sold',
        (SELECT COALESCE(SUM(quantity), 0)
         FROM warehouse.fact_orders
         WHERE run_id = :'run_id')::NUMERIC,
        3340::NUMERIC
    ),
    (
        'purchase_events',
        (SELECT COUNT(*)
         FROM warehouse.fact_events
         WHERE run_id = :'run_id'
           AND event_type = 'purchase')::NUMERIC,
        2913::NUMERIC
    ),
    (
        'behavior_events',
        (SELECT COUNT(*)
         FROM warehouse.fact_events
         WHERE run_id = :'run_id'
           AND event_type <> 'purchase')::NUMERIC,
        93595::NUMERIC
    ),
    (
        'historical_conversions',
        (SELECT COALESCE(
            SUM(historical_converted_decisions), 0)
         FROM warehouse.fact_daily_metrics
         WHERE run_id = :'run_id')::NUMERIC,
        2915::NUMERIC
    ),
    (
        'ingestion_registry_entries',
        (SELECT COUNT(*)
         FROM staging.ingestion_registry
         WHERE run_id = :'run_id')::NUMERIC,
        8::NUMERIC
    )
) AS checks(metric, actual, expected);


SELECT
    metric,
    actual,
    expected,
    CASE
        WHEN actual = expected
        THEN 'PASS'
        ELSE 'FAIL'
    END AS status
FROM warehouse_total_audit
ORDER BY metric;


-- =====================================================
-- 5. FINAL AUTOMATED ASSERTIONS
-- =====================================================

DO $$
BEGIN

    IF EXISTS (
        SELECT 1
        FROM warehouse_count_audit
        WHERE actual_rows <> expected_rows
    ) THEN
        RAISE EXCEPTION
            'Warehouse table count validation failed';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM warehouse_parity_audit
        WHERE violations <> 0
    ) THEN
        RAISE EXCEPTION
            'Warehouse source parity validation failed';
    END IF;

    IF (
        SELECT COUNT(*)
        FROM warehouse_daily_audit
    ) <> 90
    OR EXISTS (
        SELECT 1
        FROM warehouse_daily_audit
        WHERE status <> 'PASS'
    ) THEN
        RAISE EXCEPTION
            'Warehouse daily reconciliation failed';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM warehouse_total_audit
        WHERE actual IS DISTINCT FROM expected
    ) THEN
        RAISE EXCEPTION
            'Warehouse business totals validation failed';
    END IF;

    RAISE NOTICE
        'FINAL SQL WAREHOUSE RECONCILIATION PASSED.';

END
$$;

COMMIT;