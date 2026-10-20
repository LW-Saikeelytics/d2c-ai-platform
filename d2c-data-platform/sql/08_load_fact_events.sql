
-- =====================================================
-- PHASE 8.7.3 - LOAD EVENTS FACT TABLE
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
-- 1. SOURCE AND DIMENSION PREFLIGHT
-- =====================================================

DO $$
DECLARE
    v_run TEXT := current_setting('m14.run_id');
    v_events BIGINT;
    v_matched BIGINT;
    v_invalid BIGINT;
BEGIN

    SELECT COUNT(*)
    INTO v_events
    FROM staging.events
    WHERE run_id = v_run;

    IF v_events <> 96508 THEN
        RAISE EXCEPTION
            'Expected 96508 staged events, found %',
            v_events;
    END IF;

    -- Ensure every event resolves to one customer,
    -- one product, and one simulation day.

    SELECT COUNT(*)
    INTO v_matched
    FROM staging.events s

    JOIN warehouse.dim_customers c
        ON c.run_id = s.run_id
       AND c.customer_id = s.customer_id

    JOIN warehouse.dim_products p
        ON p.run_id = s.run_id
       AND p.product_id = s.product_id

    JOIN warehouse.dim_days d
        ON d.run_id = s.run_id
       AND d.simulation_day = s.simulation_day

    WHERE s.run_id = v_run;

    IF v_matched <> v_events THEN
        RAISE EXCEPTION
            'Event dimension lookup failed: % of %',
            v_matched, v_events;
    END IF;

    -- Purchase events must match the exact order,
    -- including customer, product and day keys.

    SELECT COUNT(*)
    INTO v_invalid
    FROM staging.events s

    JOIN warehouse.dim_customers c
        ON c.run_id = s.run_id
       AND c.customer_id = s.customer_id

    JOIN warehouse.dim_products p
        ON p.run_id = s.run_id
       AND p.product_id = s.product_id

    JOIN warehouse.dim_days d
        ON d.run_id = s.run_id
       AND d.simulation_day = s.simulation_day

    LEFT JOIN warehouse.fact_orders o
        ON o.run_id = s.run_id
       AND o.order_id = s.order_id

    WHERE s.run_id = v_run
      AND (
          s.event_type NOT IN (
              'product_view',
              'add_to_cart',
              'purchase_intent',
              'cart_abandonment',
              'purchase'
          )

          OR (
              s.event_type = 'purchase'
              AND (
                  s.order_id IS NULL
                  OR o.order_id IS NULL
                  OR o.day_key IS DISTINCT FROM d.day_key
                  OR o.customer_key
                     IS DISTINCT FROM c.customer_key
                  OR o.product_key
                     IS DISTINCT FROM p.product_key
              )
          )

          OR (
              s.event_type <> 'purchase'
              AND s.order_id IS NOT NULL
          )
      );

    IF v_invalid <> 0 THEN
        RAISE EXCEPTION
            'Invalid staged event/order links: %',
            v_invalid;
    END IF;

    RAISE NOTICE
        'EVENTS FACT SOURCE PREFLIGHT PASSED.';

END
$$;


-- =====================================================
-- 2. LOAD EVENTS FACT
-- =====================================================

INSERT INTO warehouse.fact_events (
    run_id,
    event_id,
    day_key,
    customer_key,
    product_key,
    event_type,
    order_id
)

SELECT
    s.run_id,
    s.event_id,

    d.day_key,
    c.customer_key,
    p.product_key,

    s.event_type,
    s.order_id

FROM staging.events s

JOIN warehouse.dim_customers c
    ON c.run_id = s.run_id
   AND c.customer_id = s.customer_id

JOIN warehouse.dim_products p
    ON p.run_id = s.run_id
   AND p.product_id = s.product_id

JOIN warehouse.dim_days d
    ON d.run_id = s.run_id
   AND d.simulation_day = s.simulation_day

WHERE s.run_id = :'run_id'

ORDER BY s.event_id

ON CONFLICT (run_id, event_id)
DO NOTHING;


-- =====================================================
-- 3. VALIDATE FACT RECORDS
-- =====================================================

DO $$
DECLARE
    v_run TEXT := current_setting('m14.run_id');

    v_fact_events BIGINT;
    v_source_events BIGINT;
    v_purchases BIGINT;
    v_non_purchases BIGINT;

BEGIN

    SELECT
        COUNT(*),
        COUNT(*) FILTER (
            WHERE event_type = 'purchase'
        ),
        COUNT(*) FILTER (
            WHERE event_type <> 'purchase'
        )
    INTO
        v_fact_events,
        v_purchases,
        v_non_purchases
    FROM warehouse.fact_events
    WHERE run_id = v_run;

    SELECT COUNT(*)
    INTO v_source_events
    FROM staging.events
    WHERE run_id = v_run;

    IF v_fact_events <> v_source_events
       OR v_fact_events <> 96508 THEN

        RAISE EXCEPTION
            'Event count mismatch: fact %, source %',
            v_fact_events, v_source_events;

    END IF;

    IF v_purchases <> 2913
       OR v_non_purchases <> 93595 THEN

        RAISE EXCEPTION
            'Event classification mismatch: purchases %, behavior %',
            v_purchases, v_non_purchases;

    END IF;

    -- Check every fact against staging and
    -- its correctly resolved dimension keys.

    IF EXISTS (
        SELECT 1

        FROM staging.events s

        JOIN warehouse.dim_customers c
            ON c.run_id = s.run_id
           AND c.customer_id = s.customer_id

        JOIN warehouse.dim_products p
            ON p.run_id = s.run_id
           AND p.product_id = s.product_id

        JOIN warehouse.dim_days d
            ON d.run_id = s.run_id
           AND d.simulation_day = s.simulation_day

        LEFT JOIN warehouse.fact_events f
            ON f.run_id = s.run_id
           AND f.event_id = s.event_id

        WHERE s.run_id = v_run
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
          )
    ) THEN

        RAISE EXCEPTION
            'Events fact differs from staging or dimensions';

    END IF;

    -- Confirm no extra warehouse events exist
    -- outside the staging source.

    IF EXISTS (
        SELECT 1

        FROM warehouse.fact_events f

        LEFT JOIN staging.events s
            ON s.run_id = f.run_id
           AND s.event_id = f.event_id

        WHERE f.run_id = v_run
          AND s.event_id IS NULL
    ) THEN

        RAISE EXCEPTION
            'Warehouse contains events absent from staging';

    END IF;

    -- Ensure purchase facts still reference
    -- matching customer, product and day keys.

    IF EXISTS (
        SELECT 1

        FROM warehouse.fact_events f

        JOIN warehouse.fact_orders o
            ON o.run_id = f.run_id
           AND o.order_id = f.order_id

        WHERE f.run_id = v_run
          AND f.event_type = 'purchase'
          AND (
              f.day_key IS DISTINCT FROM o.day_key
              OR f.customer_key
                 IS DISTINCT FROM o.customer_key
              OR f.product_key
                 IS DISTINCT FROM o.product_key
          )
    ) THEN

        RAISE EXCEPTION
            'Purchase facts do not match order dimensions';

    END IF;

    RAISE NOTICE 'EVENTS FACT VALIDATION PASSED.';

END
$$;


-- =====================================================
-- 4. DISPLAY OVERALL EVENT COUNTS
-- =====================================================

SELECT
    COUNT(*) AS fact_event_rows,

    COUNT(*) FILTER (
        WHERE event_type = 'purchase'
    ) AS purchase_events,

    COUNT(*) FILTER (
        WHERE event_type <> 'purchase'
    ) AS behavioral_events

FROM warehouse.fact_events

WHERE run_id = :'run_id';


-- =====================================================
-- 5. DAY 30 SAMPLE RECONCILIATION
-- =====================================================

SELECT
    d.simulation_day,

    COUNT(*) AS total_events,

    COUNT(*) FILTER (
        WHERE f.event_type = 'purchase'
    ) AS purchase_events,

    COUNT(*) FILTER (
        WHERE f.event_type <> 'purchase'
    ) AS behavioral_events

FROM warehouse.fact_events f

JOIN warehouse.dim_days d
    ON d.run_id = f.run_id
   AND d.day_key = f.day_key

WHERE f.run_id = :'run_id'
  AND d.simulation_day = 30

GROUP BY d.simulation_day;


COMMIT;
