
-- =====================================================
-- PHASE 8.6.1 - DREAMNEST DIMENSIONAL WAREHOUSE
-- =====================================================

\pset pager off

BEGIN;

CREATE SCHEMA IF NOT EXISTS warehouse
AUTHORIZATION dreamnest_app;


-- =====================================================
-- 1. CUSTOMER DIMENSION
-- =====================================================

CREATE TABLE IF NOT EXISTS warehouse.dim_customers (
    customer_key BIGINT GENERATED ALWAYS AS IDENTITY,
    run_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,

    segment TEXT NOT NULL,
    price_tendency TEXT NOT NULL,
    discount_sensitivity TEXT NOT NULL,
    premium_product_tendency TEXT NOT NULL,
    repeat_purchase_tendency TEXT NOT NULL,
    city_id TEXT NOT NULL,
    region TEXT NOT NULL,
    acquisition_channel TEXT NOT NULL,

    registration_day BIGINT NOT NULL,
    lifetime_orders BIGINT NOT NULL,
    lifetime_spend NUMERIC(18,2) NOT NULL,
    last_order_day BIGINT,
    preferred_categories JSONB NOT NULL,
    purchase_propensity DOUBLE PRECISION NOT NULL,
    behavior_profile TEXT NOT NULL,
    status TEXT NOT NULL,

    PRIMARY KEY (run_id, customer_key),
    UNIQUE (run_id, customer_id),

    CHECK (registration_day >= 1),
    CHECK (lifetime_orders >= 0),
    CHECK (lifetime_spend >= 0),
    CHECK (jsonb_typeof(preferred_categories) = 'array')
);


-- =====================================================
-- 2. PRODUCT DIMENSION
-- =====================================================

CREATE TABLE IF NOT EXISTS warehouse.dim_products (
    product_key BIGINT GENERATED ALWAYS AS IDENTITY,
    run_id TEXT NOT NULL,
    product_id TEXT NOT NULL,

    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT NOT NULL,
    product_type TEXT NOT NULL,
    price_band TEXT NOT NULL,
    positioning TEXT NOT NULL,

    launch_day BIGINT NOT NULL,
    discontinue_day BIGINT,

    PRIMARY KEY (run_id, product_key),
    UNIQUE (run_id, product_id),

    CHECK (launch_day >= 1),
    CHECK (
        discontinue_day IS NULL
        OR discontinue_day >= launch_day
    )
);


-- =====================================================
-- 3. SIMULATION DAY DIMENSION
-- =====================================================

CREATE TABLE IF NOT EXISTS warehouse.dim_days (
    day_key BIGINT GENERATED ALWAYS AS IDENTITY,
    run_id TEXT NOT NULL,
    simulation_day BIGINT NOT NULL,

    PRIMARY KEY (run_id, day_key),
    UNIQUE (run_id, simulation_day),

    CHECK (simulation_day >= 1)
);


-- =====================================================
-- 4. ORDERS FACT
-- =====================================================

CREATE TABLE IF NOT EXISTS warehouse.fact_orders (
    run_id TEXT NOT NULL,
    order_id TEXT NOT NULL,

    day_key BIGINT NOT NULL,
    customer_key BIGINT NOT NULL,
    product_key BIGINT NOT NULL,

    variant_id TEXT NOT NULL,
    channel TEXT NOT NULL,

    quantity BIGINT NOT NULL,
    unit_price NUMERIC(18,2) NOT NULL,
    gross_amount NUMERIC(18,2) NOT NULL,

    PRIMARY KEY (run_id, order_id),

    FOREIGN KEY (run_id, day_key)
        REFERENCES warehouse.dim_days
        (run_id, day_key),

    FOREIGN KEY (run_id, customer_key)
        REFERENCES warehouse.dim_customers
        (run_id, customer_key),

    FOREIGN KEY (run_id, product_key)
        REFERENCES warehouse.dim_products
        (run_id, product_key),

    CHECK (quantity > 0),
    CHECK (unit_price >= 0),
    CHECK (gross_amount >= 0)
);


-- =====================================================
-- 5. EVENTS FACT
-- =====================================================

CREATE TABLE IF NOT EXISTS warehouse.fact_events (
    run_id TEXT NOT NULL,
    event_id TEXT NOT NULL,

    day_key BIGINT NOT NULL,
    customer_key BIGINT NOT NULL,
    product_key BIGINT NOT NULL,

    event_type TEXT NOT NULL,
    order_id TEXT,

    PRIMARY KEY (run_id, event_id),

    FOREIGN KEY (run_id, day_key)
        REFERENCES warehouse.dim_days
        (run_id, day_key),

    FOREIGN KEY (run_id, customer_key)
        REFERENCES warehouse.dim_customers
        (run_id, customer_key),

    FOREIGN KEY (run_id, product_key)
        REFERENCES warehouse.dim_products
        (run_id, product_key),

    FOREIGN KEY (run_id, order_id)
        REFERENCES warehouse.fact_orders
        (run_id, order_id),

    CHECK (
        event_type IN (
            'product_view',
            'add_to_cart',
            'purchase_intent',
            'cart_abandonment',
            'purchase'
        )
    ),

    CHECK (
        (event_type = 'purchase' AND order_id IS NOT NULL)
        OR
        (event_type <> 'purchase' AND order_id IS NULL)
    )
);


-- =====================================================
-- 6. DAILY METRICS FACT
-- =====================================================

CREATE TABLE IF NOT EXISTS warehouse.fact_daily_metrics (
    run_id TEXT NOT NULL,
    day_key BIGINT NOT NULL,

    customers BIGINT NOT NULL,
    purchasing_customers BIGINT NOT NULL,
    behavior_active_customers BIGINT NOT NULL,

    behavior_event_count BIGINT NOT NULL,
    conversion_decisions_evaluated BIGINT NOT NULL,
    historical_converted_decisions BIGINT NOT NULL,

    clean_order_count BIGINT NOT NULL,
    clean_purchase_event_count BIGINT NOT NULL,
    clean_event_count BIGINT NOT NULL,

    gross_revenue NUMERIC(18,2) NOT NULL,

    PRIMARY KEY (run_id, day_key),

    FOREIGN KEY (run_id, day_key)
        REFERENCES warehouse.dim_days
        (run_id, day_key),

    CHECK (customers >= 0),
    CHECK (purchasing_customers >= 0),
    CHECK (behavior_active_customers >= 0),
    CHECK (behavior_event_count >= 0),
    CHECK (conversion_decisions_evaluated >= 0),
    CHECK (historical_converted_decisions >= 0),
    CHECK (clean_order_count >= 0),
    CHECK (clean_purchase_event_count >= 0),
    CHECK (clean_event_count >= 0),
    CHECK (gross_revenue >= 0),

    CHECK (purchasing_customers <= customers),
    CHECK (behavior_active_customers <= customers),

    CHECK (
        clean_order_count = clean_purchase_event_count
    ),

    CHECK (
        clean_event_count =
        behavior_event_count + clean_purchase_event_count
    )
);


-- =====================================================
-- QUERY PERFORMANCE INDEXES
-- =====================================================

CREATE INDEX IF NOT EXISTS idx_fact_orders_day
ON warehouse.fact_orders (run_id, day_key);

CREATE INDEX IF NOT EXISTS idx_fact_orders_product
ON warehouse.fact_orders (run_id, product_key);

CREATE INDEX IF NOT EXISTS idx_fact_events_day
ON warehouse.fact_events (run_id, day_key);

CREATE INDEX IF NOT EXISTS idx_fact_events_type
ON warehouse.fact_events (run_id, event_type);


COMMIT;


-- =====================================================
-- WAREHOUSE STRUCTURE VALIDATION
-- =====================================================

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'warehouse'
  AND table_type = 'BASE TABLE'
ORDER BY table_name;

SELECT COUNT(*) AS warehouse_table_count
FROM information_schema.tables
WHERE table_schema = 'warehouse'
  AND table_type = 'BASE TABLE';
