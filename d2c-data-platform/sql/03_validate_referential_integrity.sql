
-- =====================================================
-- PHASE 8.5.5.2
-- REFERENTIAL INTEGRITY & DAILY RECONCILIATION
-- =====================================================

\pset pager off
\set run_id 'simulation_run_20261004_120957'

BEGIN;

-- =====================================================
-- 1. REFERENTIAL & BUSINESS-RULE CHECKS
-- =====================================================

CREATE TEMP TABLE relationship_audit
ON COMMIT DROP AS

WITH
c AS (
    SELECT * FROM staging.customers
    WHERE run_id = :'run_id'
),
p AS (
    SELECT * FROM staging.product_master
    WHERE run_id = :'run_id'
),
o AS (
    SELECT * FROM staging.orders
    WHERE run_id = :'run_id'
),
e AS (
    SELECT * FROM staging.events
    WHERE run_id = :'run_id'
),
b AS (
    SELECT * FROM staging.behavior_history
    WHERE run_id = :'run_id'
),
v AS (
    SELECT * FROM staging.conversion_history
    WHERE run_id = :'run_id'
),
d AS (
    SELECT * FROM staging.daily_metrics_cleaned
    WHERE run_id = :'run_id'
),
s AS (
    SELECT * FROM staging.daily_metrics_source
    WHERE run_id = :'run_id'
),
pe AS (
    SELECT * FROM e WHERE event_type = 'purchase'
),
ne AS (
    SELECT * FROM e WHERE event_type <> 'purchase'
),
customer_order_totals AS (
    SELECT
        customer_id,
        COUNT(*) AS order_count,
        SUM(gross_amount) AS revenue,
        MAX(simulation_day) AS last_day
    FROM o
    GROUP BY customer_id
)

SELECT *
FROM (
    VALUES

    -- Orders must reference real customers/products.

    ('orders_missing_customers',
        (SELECT COUNT(*) FROM o
         LEFT JOIN c USING (customer_id)
         WHERE c.customer_id IS NULL)),

    ('orders_missing_products',
        (SELECT COUNT(*) FROM o
         LEFT JOIN p USING (product_id)
         WHERE p.product_id IS NULL)),

    ('orders_outside_product_lifecycle',
        (SELECT COUNT(*) FROM o
         JOIN p USING (product_id)
         WHERE o.simulation_day < p.launch_day
            OR (
                p.discontinue_day IS NOT NULL
                AND o.simulation_day > p.discontinue_day
            ))),

    -- Events must reference real customers/products.

    ('events_missing_customers',
        (SELECT COUNT(*) FROM e
         LEFT JOIN c USING (customer_id)
         WHERE c.customer_id IS NULL)),

    ('events_missing_products',
        (SELECT COUNT(*) FROM e
         LEFT JOIN p USING (product_id)
         WHERE p.product_id IS NULL)),

    ('events_outside_product_lifecycle',
        (SELECT COUNT(*) FROM e
         JOIN p USING (product_id)
         WHERE e.simulation_day < p.launch_day
            OR (
                p.discontinue_day IS NOT NULL
                AND e.simulation_day > p.discontinue_day
            ))),

    -- Behavior history must be valid.

    ('behavior_missing_customers',
        (SELECT COUNT(*) FROM b
         LEFT JOIN c USING (customer_id)
         WHERE c.customer_id IS NULL)),

    ('behavior_missing_products',
        (SELECT COUNT(*) FROM b
         LEFT JOIN p USING (product_id)
         WHERE p.product_id IS NULL)),

    ('behavior_outside_product_lifecycle',
        (SELECT COUNT(*) FROM b
         JOIN p USING (product_id)
         WHERE b.simulation_day < p.launch_day
            OR (
                p.discontinue_day IS NOT NULL
                AND b.simulation_day > p.discontinue_day
            ))),

    -- Historical conversion records.

    ('conversions_missing_customers',
        (SELECT COUNT(*) FROM v
         LEFT JOIN c USING (customer_id)
         WHERE c.customer_id IS NULL)),

    ('invalid_conversion_decisions',
        (SELECT COUNT(*) FROM v
         WHERE jsonb_typeof(
             result_json -> 'converted'
         ) IS DISTINCT FROM 'boolean')),

    -- Behavior history must match non-purchase events.

    ('behavior_event_mismatches',
        (SELECT COUNT(*)
         FROM b
         FULL OUTER JOIN ne
             ON b.event_id = ne.event_id
         WHERE b.event_id IS NULL
            OR ne.event_id IS NULL
            OR b.simulation_day
                IS DISTINCT FROM ne.simulation_day
            OR b.customer_id
                IS DISTINCT FROM ne.customer_id
            OR b.product_id
                IS DISTINCT FROM ne.product_id
            OR b.event_type
                IS DISTINCT FROM ne.event_type
            OR b.category
                IS DISTINCT FROM ne.category)),

    -- Every purchase event must match an order.

    ('purchase_order_mismatches',
        (SELECT COUNT(*)
         FROM o
         FULL OUTER JOIN pe
             ON o.order_id = pe.order_id
         WHERE o.order_id IS NULL
            OR pe.event_id IS NULL
            OR o.simulation_day
                IS DISTINCT FROM pe.simulation_day
            OR o.customer_id
                IS DISTINCT FROM pe.customer_id
            OR o.product_id
                IS DISTINCT FROM pe.product_id)),

    ('duplicate_purchase_order_links',
        (SELECT COUNT(*)
         FROM (
             SELECT order_id
             FROM pe
             WHERE order_id IS NOT NULL
             GROUP BY order_id
             HAVING COUNT(*) > 1
         ) duplicate_orders)),

    ('nonpurchase_events_with_order_ids',
        (SELECT COUNT(*) FROM ne
         WHERE order_id IS NOT NULL)),

    ('unknown_event_types',
        (SELECT COUNT(*) FROM e
         WHERE event_type NOT IN (
             'product_view',
             'add_to_cart',
             'purchase_intent',
             'cart_abandonment',
             'purchase'
         ))),

    -- All time-based records must fall within 90 days.

    ('activity_outside_days_1_to_90',
        (SELECT COUNT(*)
         FROM (
             SELECT simulation_day FROM o
             UNION ALL
             SELECT simulation_day FROM e
             UNION ALL
             SELECT simulation_day FROM b
             UNION ALL
             SELECT simulation_day FROM v
             UNION ALL
             SELECT simulation_day FROM d
             UNION ALL
             SELECT simulation_day FROM s
         ) activity
         WHERE simulation_day NOT BETWEEN 1 AND 90)),

    -- Customer lifetime totals must match valid orders.

    ('customer_purchase_history_mismatches',
        (SELECT COUNT(*)
         FROM c
         LEFT JOIN customer_order_totals t
             USING (customer_id)
         WHERE c.lifetime_orders
                <> COALESCE(t.order_count, 0)
            OR c.lifetime_spend
                <> COALESCE(t.revenue, 0)
            OR c.last_order_day
                IS DISTINCT FROM t.last_day))

) AS checks(check_name, violations);


SELECT
    check_name,
    violations,
    CASE
        WHEN violations = 0 THEN 'PASS'
        ELSE 'FAIL'
    END AS status
FROM relationship_audit
ORDER BY check_name;


-- =====================================================
-- 2. INDEPENDENT DAILY RECONCILIATION
-- =====================================================

CREATE TEMP TABLE daily_reconciliation_audit
ON COMMIT DROP AS

WITH
days AS (
    SELECT generate_series(
        1, 90
    )::BIGINT AS simulation_day
),

daily_orders AS (
    SELECT
        simulation_day,
        COUNT(*) AS order_count
    FROM staging.orders
    WHERE run_id = :'run_id'
    GROUP BY simulation_day
),

daily_behavior AS (
    SELECT
        simulation_day,
        COUNT(*) AS behavior_count,
        COUNT(DISTINCT customer_id) AS active_customers
    FROM staging.behavior_history
    WHERE run_id = :'run_id'
    GROUP BY simulation_day
),

daily_events AS (
    SELECT
        simulation_day,
        COUNT(*) AS event_count,
        COUNT(*) FILTER (
            WHERE event_type = 'purchase'
        ) AS purchase_count
    FROM staging.events
    WHERE run_id = :'run_id'
    GROUP BY simulation_day
),

daily_conversions AS (
    SELECT
        simulation_day,
        COUNT(*) AS evaluated_count,
        COUNT(*) FILTER (
            WHERE result_json ->> 'converted' = 'true'
        ) AS converted_count
    FROM staging.conversion_history
    WHERE run_id = :'run_id'
    GROUP BY simulation_day
)

SELECT
    days.simulation_day,

    COALESCE(o.order_count, 0) AS actual_orders,

    COALESCE(b.behavior_count, 0) AS actual_behaviors,

    COALESCE(e.event_count, 0) AS actual_events,

    COALESCE(v.evaluated_count, 0) AS actual_decisions,

    CASE
        WHEN clean.simulation_day IS NULL
          OR source.simulation_day IS NULL

          OR clean.customers <> 10000

          OR clean.clean_order_count
                <> COALESCE(o.order_count, 0)

          OR clean.behavior_event_count
                <> COALESCE(b.behavior_count, 0)

          OR clean.behavior_active_customers
                <> COALESCE(b.active_customers, 0)

          OR clean.clean_event_count
                <> COALESCE(e.event_count, 0)

          OR clean.clean_purchase_event_count
                <> COALESCE(e.purchase_count, 0)

          OR clean.conversion_decisions_evaluated
                <> COALESCE(v.evaluated_count, 0)

          OR clean.historical_converted_decisions
                <> COALESCE(v.converted_count, 0)

          OR COALESCE(o.order_count, 0)
                <> COALESCE(e.purchase_count, 0)

        THEN 1
        ELSE 0
    END AS mismatch

FROM days

LEFT JOIN staging.daily_metrics_cleaned clean
    ON clean.simulation_day = days.simulation_day
   AND clean.run_id = :'run_id'

LEFT JOIN staging.daily_metrics_source source
    ON source.simulation_day = days.simulation_day
   AND source.run_id = :'run_id'

LEFT JOIN daily_orders o
    USING (simulation_day)

LEFT JOIN daily_behavior b
    USING (simulation_day)

LEFT JOIN daily_events e
    USING (simulation_day)

LEFT JOIN daily_conversions v
    USING (simulation_day);


-- Overall daily validation.

SELECT
    COUNT(*) AS days_checked,
    SUM(mismatch) AS days_with_mismatches
FROM daily_reconciliation_audit;


-- Display Day 30 as a sample reconciliation.

SELECT
    simulation_day,
    actual_orders,
    actual_behaviors,
    actual_events,
    actual_decisions,
    CASE
        WHEN mismatch = 0 THEN 'PASS'
        ELSE 'FAIL'
    END AS status
FROM daily_reconciliation_audit
WHERE simulation_day = 30;


-- =====================================================
-- 3. FAIL IF ANY VALIDATION FAILED
-- =====================================================

DO $$
BEGIN

    IF EXISTS (
        SELECT 1
        FROM relationship_audit
        WHERE violations <> 0
    ) THEN

        RAISE EXCEPTION
            'SQL referential integrity validation failed';

    END IF;

    IF EXISTS (
        SELECT 1
        FROM daily_reconciliation_audit
        WHERE mismatch <> 0
    ) THEN

        RAISE EXCEPTION
            'SQL daily reconciliation failed';

    END IF;

    RAISE NOTICE
        'POSTGRESQL REFERENTIAL INTEGRITY AND DAILY RECONCILIATION PASSED.';

END
$$;

COMMIT;
