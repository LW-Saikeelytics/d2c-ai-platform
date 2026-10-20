
-- =====================================================
-- PHASE 8.7.1 - LOAD WAREHOUSE DIMENSIONS
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
-- 1. PREFLIGHT: VALIDATE STAGING COUNTS
-- =====================================================

DO $$
DECLARE
    v_run TEXT := current_setting('m14.run_id');
BEGIN

    IF (
        SELECT COUNT(*)
        FROM staging.customers
        WHERE run_id = v_run
    ) <> 10000 THEN
        RAISE EXCEPTION
            'Expected 10000 staging customers';
    END IF;

    IF (
        SELECT COUNT(*)
        FROM staging.product_master
        WHERE run_id = v_run
    ) <> 29 THEN
        RAISE EXCEPTION
            'Expected 29 staging products';
    END IF;

    IF (
        SELECT COUNT(*)
        FROM staging.daily_metrics_cleaned
        WHERE run_id = v_run
    ) <> 90 THEN
        RAISE EXCEPTION
            'Expected 90 staging days';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM staging.daily_metrics_cleaned
        WHERE run_id = v_run
          AND simulation_day NOT BETWEEN 1 AND 90
    ) THEN
        RAISE EXCEPTION
            'Simulation day outside 1-90';
    END IF;

    RAISE NOTICE 'DIMENSION SOURCE PREFLIGHT PASSED.';

END
$$;


-- =====================================================
-- 2. DAY DIMENSION
-- =====================================================

INSERT INTO warehouse.dim_days (
    run_id,
    simulation_day
)
SELECT
    run_id,
    simulation_day
FROM staging.daily_metrics_cleaned
WHERE run_id = :'run_id'
ORDER BY simulation_day

ON CONFLICT (run_id, simulation_day)
DO NOTHING;


-- =====================================================
-- 3. CUSTOMER DIMENSION
-- =====================================================

INSERT INTO warehouse.dim_customers (
    run_id,
    customer_id,
    segment,
    price_tendency,
    discount_sensitivity,
    premium_product_tendency,
    repeat_purchase_tendency,
    city_id,
    region,
    acquisition_channel,
    registration_day,
    lifetime_orders,
    lifetime_spend,
    last_order_day,
    preferred_categories,
    purchase_propensity,
    behavior_profile,
    status
)
SELECT
    run_id,
    customer_id,
    segment,
    price_tendency,
    discount_sensitivity,
    premium_product_tendency,
    repeat_purchase_tendency,
    city_id,
    region,
    acquisition_channel,
    registration_day,
    lifetime_orders,
    lifetime_spend,
    last_order_day,
    preferred_categories,
    purchase_propensity,
    behavior_profile,
    status
FROM staging.customers
WHERE run_id = :'run_id'
ORDER BY customer_id

ON CONFLICT (run_id, customer_id)
DO NOTHING;


-- =====================================================
-- 4. PRODUCT DIMENSION
-- =====================================================

INSERT INTO warehouse.dim_products (
    run_id,
    product_id,
    product_name,
    category,
    subcategory,
    product_type,
    price_band,
    positioning,
    launch_day,
    discontinue_day
)
SELECT
    run_id,
    product_id,
    product_name,
    category,
    subcategory,
    product_type,
    price_band,
    positioning,
    launch_day,
    discontinue_day
FROM staging.product_master
WHERE run_id = :'run_id'
ORDER BY product_id

ON CONFLICT (run_id, product_id)
DO NOTHING;


-- =====================================================
-- 5. VERIFY ROW COUNTS AND SOURCE PARITY
-- =====================================================

DO $$
DECLARE
    v_run TEXT := current_setting('m14.run_id');
    v_customers BIGINT;
    v_products BIGINT;
    v_days BIGINT;
BEGIN

    SELECT COUNT(*) INTO v_customers
    FROM warehouse.dim_customers
    WHERE run_id = v_run;

    SELECT COUNT(*) INTO v_products
    FROM warehouse.dim_products
    WHERE run_id = v_run;

    SELECT COUNT(*) INTO v_days
    FROM warehouse.dim_days
    WHERE run_id = v_run;

    IF v_customers <> 10000
       OR v_products <> 29
       OR v_days <> 90 THEN

        RAISE EXCEPTION
            'Dimension counts mismatch: %, %, %',
            v_customers, v_products, v_days;
    END IF;

    -- Compare every customer field with staging.
    -- Exclude the generated surrogate key.

    IF EXISTS (
        SELECT 1
        FROM staging.customers s
        LEFT JOIN warehouse.dim_customers d
          ON d.run_id = s.run_id
         AND d.customer_id = s.customer_id
        WHERE s.run_id = v_run
          AND (
              d.customer_key IS NULL
              OR (to_jsonb(d) - 'customer_key')
                 IS DISTINCT FROM to_jsonb(s)
          )
    ) THEN
        RAISE EXCEPTION
            'Customer dimension differs from staging';
    END IF;

    -- Compare every product field.

    IF EXISTS (
        SELECT 1
        FROM staging.product_master s
        LEFT JOIN warehouse.dim_products d
          ON d.run_id = s.run_id
         AND d.product_id = s.product_id
        WHERE s.run_id = v_run
          AND (
              d.product_key IS NULL
              OR (to_jsonb(d) - 'product_key')
                 IS DISTINCT FROM to_jsonb(s)
          )
    ) THEN
        RAISE EXCEPTION
            'Product dimension differs from staging';
    END IF;

    -- Compare simulation days.

    IF EXISTS (
        SELECT 1
        FROM staging.daily_metrics_cleaned s
        LEFT JOIN warehouse.dim_days d
          ON d.run_id = s.run_id
         AND d.simulation_day = s.simulation_day
        WHERE s.run_id = v_run
          AND d.day_key IS NULL
    ) THEN
        RAISE EXCEPTION
            'Day dimension differs from staging';
    END IF;

    -- Customer revenue must match clean orders.

    IF (
        SELECT COALESCE(SUM(lifetime_spend), 0)
        FROM warehouse.dim_customers
        WHERE run_id = v_run
    ) <> (
        SELECT COALESCE(SUM(gross_amount), 0)
        FROM staging.orders
        WHERE run_id = v_run
    ) THEN
        RAISE EXCEPTION
            'Customer dimension revenue mismatch';
    END IF;

    RAISE NOTICE 'DIMENSION LOAD VALIDATION PASSED.';

END
$$;


-- =====================================================
-- 6. DISPLAY RESULTS
-- =====================================================

SELECT
    'dim_customers' AS dimension,
    COUNT(*) AS row_count
FROM warehouse.dim_customers
WHERE run_id = :'run_id'

UNION ALL

SELECT
    'dim_products',
    COUNT(*)
FROM warehouse.dim_products
WHERE run_id = :'run_id'

UNION ALL

SELECT
    'dim_days',
    COUNT(*)
FROM warehouse.dim_days
WHERE run_id = :'run_id';


SELECT
    COALESCE(SUM(lifetime_spend), 0)
        AS customer_revenue_inr
FROM warehouse.dim_customers
WHERE run_id = :'run_id';


COMMIT;
