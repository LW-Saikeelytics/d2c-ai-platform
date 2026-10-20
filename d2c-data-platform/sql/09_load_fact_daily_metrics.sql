-- =====================================================
-- PHASE 8.7.4 - LOAD DAILY METRICS FACT
-- =====================================================

\pset pager off
\set run_id 'simulation_run_20261004_120957'

BEGIN;

SELECT set_config(
    'm14.run_id',
    :'run_id',
    true
) AS active_run;


-- =====================================================
-- 1. INDEPENDENTLY CALCULATE DAILY BUSINESS TOTALS
-- =====================================================

CREATE TEMP TABLE expected_daily
ON COMMIT DROP AS

WITH order_totals AS (

    SELECT
        run_id,
        day_key,
        COUNT(*) AS order_count,
        COUNT(DISTINCT customer_key) AS purchasing_customers,
        SUM(gross_amount) AS gross_revenue

    FROM warehouse.fact_orders

    WHERE run_id = :'run_id'

    GROUP BY run_id, day_key

),

event_totals AS (

    SELECT
        run_id,
        day_key,

        COUNT(*) AS total_events,

        COUNT(*) FILTER (
            WHERE event_type = 'purchase'
        ) AS purchase_events,

        COUNT(*) FILTER (
            WHERE event_type <> 'purchase'
        ) AS behavior_events

    FROM warehouse.fact_events

    WHERE run_id = :'run_id'

    GROUP BY run_id, day_key

)

SELECT
    d.run_id,
    d.day_key,
    d.simulation_day,

    s.customers,

    COALESCE(
        o.purchasing_customers, 0
    ) AS purchasing_customers,

    s.behavior_active_customers,
    s.behavior_event_count,
    s.conversion_decisions_evaluated,
    s.historical_converted_decisions,

    s.clean_order_count,
    s.clean_purchase_event_count,
    s.clean_event_count,

    COALESCE(
        o.gross_revenue, 0
    )::NUMERIC(18,2) AS gross_revenue,

    -- Independent warehouse totals used
    -- for validation before loading.

    COALESCE(
        o.order_count, 0
    ) AS actual_orders,

    COALESCE(
        e.total_events, 0
    ) AS actual_events,

    COALESCE(
        e.purchase_events, 0
    ) AS actual_purchases,

    COALESCE(
        e.behavior_events, 0
    ) AS actual_behaviors

FROM warehouse.dim_days d

JOIN staging.daily_metrics_cleaned s
    ON s.run_id = d.run_id
   AND s.simulation_day = d.simulation_day

LEFT JOIN order_totals o
    ON o.run_id = d.run_id
   AND o.day_key = d.day_key

LEFT JOIN event_totals e
    ON e.run_id = d.run_id
   AND e.day_key = d.day_key

WHERE d.run_id = :'run_id';


-- =====================================================
-- 2. SOURCE PREFLIGHT
-- =====================================================

DO $$
DECLARE
    v_run TEXT := current_setting('m14.run_id');
    v_rows BIGINT;
    v_revenue NUMERIC(18,2);

BEGIN

    IF (
        SELECT COUNT(*)
        FROM warehouse.dim_days
        WHERE run_id = v_run
    ) <> 90 THEN
        RAISE EXCEPTION
            'Expected 90 warehouse days';
    END IF;

    IF (
        SELECT COUNT(*)
        FROM staging.daily_metrics_cleaned
        WHERE run_id = v_run
    ) <> 90 THEN
        RAISE EXCEPTION
            'Expected 90 cleaned daily source rows';
    END IF;

    SELECT COUNT(*)
    INTO v_rows
    FROM expected_daily;

    IF v_rows <> 90 THEN
        RAISE EXCEPTION
            'Expected 90 matched daily rows, found %',
            v_rows;
    END IF;

    -- Confirm days 1 through 90 are represented.

    IF EXISTS (
        SELECT day_number
        FROM generate_series(1, 90)
            AS day_number

        EXCEPT

        SELECT simulation_day
        FROM expected_daily
    ) THEN
        RAISE EXCEPTION
            'Missing simulation days';
    END IF;

    -- Compare independently calculated
    -- warehouse totals to cleaned daily data.

    IF EXISTS (
        SELECT 1
        FROM expected_daily

        WHERE clean_order_count <> actual_orders

           OR clean_event_count <> actual_events

           OR clean_purchase_event_count
                <> actual_purchases

           OR behavior_event_count
                <> actual_behaviors

           OR customers <> 10000
    ) THEN
        RAISE EXCEPTION
            'Daily source and warehouse facts disagree';
    END IF;

    SELECT COALESCE(
        SUM(gross_revenue), 0
    )
    INTO v_revenue
    FROM expected_daily;

    IF v_revenue <> 53812160.00 THEN
        RAISE EXCEPTION
            'Unexpected revenue: %',
            v_revenue;
    END IF;

    IF (
        SELECT SUM(clean_order_count)
        FROM expected_daily
    ) <> 2913 THEN
        RAISE EXCEPTION
            'Daily order total mismatch';
    END IF;

    IF (
        SELECT SUM(clean_event_count)
        FROM expected_daily
    ) <> 96508 THEN
        RAISE EXCEPTION
            'Daily event total mismatch';
    END IF;

    IF (
        SELECT SUM(historical_converted_decisions)
        FROM expected_daily
    ) <> 2915 THEN
        RAISE EXCEPTION
            'Historical conversion total mismatch';
    END IF;

    RAISE NOTICE
        'DAILY METRICS FACT SOURCE PREFLIGHT PASSED.';

END
$$;


-- =====================================================
-- 3. LOAD DAILY METRICS FACT
-- =====================================================

INSERT INTO warehouse.fact_daily_metrics (
    run_id,
    day_key,

    customers,
    purchasing_customers,
    behavior_active_customers,

    behavior_event_count,
    conversion_decisions_evaluated,
    historical_converted_decisions,

    clean_order_count,
    clean_purchase_event_count,
    clean_event_count,

    gross_revenue
)

SELECT
    run_id,
    day_key,

    customers,
    purchasing_customers,
    behavior_active_customers,

    behavior_event_count,
    conversion_decisions_evaluated,
    historical_converted_decisions,

    clean_order_count,
    clean_purchase_event_count,
    clean_event_count,

    gross_revenue

FROM expected_daily

ORDER BY simulation_day

ON CONFLICT (run_id, day_key)
DO NOTHING;


-- =====================================================
-- 4. VALIDATE EVERY DAILY FACT
-- =====================================================

DO $$
DECLARE
    v_run TEXT := current_setting('m14.run_id');
    v_count BIGINT;
    v_revenue NUMERIC(18,2);

BEGIN

    SELECT
        COUNT(*),
        COALESCE(SUM(gross_revenue), 0)

    INTO
        v_count,
        v_revenue

    FROM warehouse.fact_daily_metrics

    WHERE run_id = v_run;

    IF v_count <> 90 THEN
        RAISE EXCEPTION
            'Expected 90 daily facts, found %',
            v_count;
    END IF;

    IF v_revenue <> 53812160.00 THEN
        RAISE EXCEPTION
            'Daily fact revenue mismatch: %',
            v_revenue;
    END IF;

    -- Detect missing or stale facts, including
    -- differences hidden by matching totals.

    IF EXISTS (

        SELECT 1

        FROM expected_daily e

        LEFT JOIN warehouse.fact_daily_metrics f
            ON f.run_id = e.run_id
           AND f.day_key = e.day_key

        WHERE f.day_key IS NULL

           OR ROW(
                f.customers,
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
                e.customers,
                e.purchasing_customers,
                e.behavior_active_customers,
                e.behavior_event_count,
                e.conversion_decisions_evaluated,
                e.historical_converted_decisions,
                e.clean_order_count,
                e.clean_purchase_event_count,
                e.clean_event_count,
                e.gross_revenue
           )
    ) THEN
        RAISE EXCEPTION
            'Daily fact differs from expected metrics';
    END IF;

    RAISE NOTICE
        'DAILY METRICS FACT VALIDATION PASSED.';

END
$$;


-- =====================================================
-- 5. DISPLAY FINAL RESULTS
-- =====================================================

SELECT
    COUNT(*) AS daily_fact_rows,

    SUM(clean_order_count) AS total_orders,

    SUM(clean_event_count) AS total_events,

    SUM(historical_converted_decisions)
        AS historical_conversions,

    SUM(gross_revenue) AS total_revenue_inr

FROM warehouse.fact_daily_metrics

WHERE run_id = :'run_id';


-- =====================================================
-- 6. DAY 30 SAMPLE
-- =====================================================

SELECT
    d.simulation_day,

    f.purchasing_customers,
    f.clean_order_count,
    f.behavior_event_count,
    f.clean_event_count,
    f.conversion_decisions_evaluated,
    f.historical_converted_decisions,
    f.gross_revenue

FROM warehouse.fact_daily_metrics f

JOIN warehouse.dim_days d
    ON d.run_id = f.run_id
   AND d.day_key = f.day_key

WHERE f.run_id = :'run_id'
  AND d.simulation_day = 30;


COMMIT;