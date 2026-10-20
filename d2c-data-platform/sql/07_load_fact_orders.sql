
-- =====================================================
-- PHASE 8.7.2 - LOAD ORDERS FACT TABLE
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
    v_orders BIGINT;
    v_matched BIGINT;
BEGIN

    SELECT COUNT(*)
    INTO v_orders
    FROM staging.orders
    WHERE run_id = v_run;

    IF v_orders <> 2913 THEN
        RAISE EXCEPTION
            'Expected 2913 staged orders, found %',
            v_orders;
    END IF;

    -- Verify that every order resolves to
    -- exactly one customer, product and day.

    SELECT COUNT(*)
    INTO v_matched
    FROM staging.orders s

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

    IF v_matched <> v_orders THEN
        RAISE EXCEPTION
            'Dimension lookup failed: matched % of % orders',
            v_matched, v_orders;
    END IF;

    RAISE NOTICE
        'ORDERS FACT SOURCE PREFLIGHT PASSED.';

END
$$;


-- =====================================================
-- 2. LOAD ORDERS FACT
-- =====================================================

INSERT INTO warehouse.fact_orders (
    run_id,
    order_id,
    day_key,
    customer_key,
    product_key,
    variant_id,
    channel,
    quantity,
    unit_price,
    gross_amount
)

SELECT
    s.run_id,
    s.order_id,

    d.day_key,
    c.customer_key,
    p.product_key,

    s.variant_id,
    s.channel,
    s.quantity,
    s.unit_price,
    s.gross_amount

FROM staging.orders s

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

ORDER BY s.order_id

ON CONFLICT (run_id, order_id)
DO NOTHING;


-- =====================================================
-- 3. VALIDATE FACT ROWS AND REVENUE
-- =====================================================

DO $$
DECLARE
    v_run TEXT := current_setting('m14.run_id');

    v_fact_orders BIGINT;
    v_source_orders BIGINT;

    v_fact_revenue NUMERIC(18,2);
    v_source_revenue NUMERIC(18,2);

BEGIN

    SELECT
        COUNT(*),
        COALESCE(SUM(gross_amount), 0)
    INTO
        v_fact_orders,
        v_fact_revenue
    FROM warehouse.fact_orders
    WHERE run_id = v_run;

    SELECT
        COUNT(*),
        COALESCE(SUM(gross_amount), 0)
    INTO
        v_source_orders,
        v_source_revenue
    FROM staging.orders
    WHERE run_id = v_run;

    IF v_fact_orders <> v_source_orders
       OR v_fact_orders <> 2913 THEN

        RAISE EXCEPTION
            'Order count mismatch: fact %, source %',
            v_fact_orders, v_source_orders;

    END IF;

    IF v_fact_revenue <> v_source_revenue
       OR v_fact_revenue <> 53812160.00 THEN

        RAISE EXCEPTION
            'Order revenue mismatch: fact %, source %',
            v_fact_revenue, v_source_revenue;

    END IF;

    -- Compare every fact against its staging order,
    -- including resolved dimension keys.
    -- This detects stale or incorrect existing facts
    -- even when counts and revenue match.

    IF EXISTS (
        SELECT 1

        FROM staging.orders s

        JOIN warehouse.dim_customers c
            ON c.run_id = s.run_id
           AND c.customer_id = s.customer_id

        JOIN warehouse.dim_products p
            ON p.run_id = s.run_id
           AND p.product_id = s.product_id

        JOIN warehouse.dim_days d
            ON d.run_id = s.run_id
           AND d.simulation_day = s.simulation_day

        LEFT JOIN warehouse.fact_orders f
            ON f.run_id = s.run_id
           AND f.order_id = s.order_id

        WHERE s.run_id = v_run

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
    ) THEN

        RAISE EXCEPTION
            'Orders fact differs from staging or dimensions';

    END IF;

    RAISE NOTICE 'ORDERS FACT VALIDATION PASSED.';

END
$$;


-- =====================================================
-- 4. DISPLAY FINAL RESULTS
-- =====================================================

SELECT
    COUNT(*) AS fact_order_rows,
    COALESCE(SUM(quantity), 0) AS units_sold,
    COALESCE(SUM(gross_amount), 0)
        AS gross_revenue_inr
FROM warehouse.fact_orders
WHERE run_id = :'run_id';


-- Sample: Day 30 orders

SELECT
    d.simulation_day,
    COUNT(*) AS orders,
    COALESCE(SUM(f.gross_amount), 0)
        AS gross_revenue_inr

FROM warehouse.fact_orders f

JOIN warehouse.dim_days d
    ON d.run_id = f.run_id
   AND d.day_key = f.day_key

WHERE f.run_id = :'run_id'
  AND d.simulation_day = 30

GROUP BY d.simulation_day;


COMMIT;
