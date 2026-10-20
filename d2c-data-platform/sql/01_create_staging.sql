
-- =====================================================
-- M14 DREAMNEST DATA PLATFORM
-- PHASE 8.5.4.1 - POSTGRESQL STAGING TABLES
-- =====================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS staging
AUTHORIZATION dreamnest_app;


-- =====================================================
-- 1. CUSTOMERS
-- =====================================================

CREATE TABLE IF NOT EXISTS staging.customers (
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

    PRIMARY KEY (run_id, customer_id),

    CHECK (jsonb_typeof(preferred_categories) = 'array')
);


-- =====================================================
-- 2. PRODUCT MASTER
-- =====================================================

CREATE TABLE IF NOT EXISTS staging.product_master (
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

    PRIMARY KEY (run_id, product_id)
);


-- =====================================================
-- 3. CLEANED ORDERS
-- =====================================================

CREATE TABLE IF NOT EXISTS staging.orders (
    run_id TEXT NOT NULL,
    simulation_day BIGINT NOT NULL,
    order_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    segment TEXT NOT NULL,
    city_id TEXT NOT NULL,
    region TEXT NOT NULL,
    channel TEXT NOT NULL,
    product_id TEXT NOT NULL,
    variant_id TEXT NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT NOT NULL,
    quantity BIGINT NOT NULL,
    unit_price NUMERIC(18,2) NOT NULL,
    gross_amount NUMERIC(18,2) NOT NULL,

    PRIMARY KEY (run_id, order_id)
);


-- =====================================================
-- 4. CLEANED EVENTS
-- =====================================================

CREATE TABLE IF NOT EXISTS staging.events (
    run_id TEXT NOT NULL,
    simulation_day BIGINT NOT NULL,
    event_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    product_id TEXT NOT NULL,
    category TEXT NOT NULL,
    order_id TEXT,

    PRIMARY KEY (run_id, event_id)
);


-- =====================================================
-- 5. CLEANED BEHAVIOR HISTORY
-- =====================================================

CREATE TABLE IF NOT EXISTS staging.behavior_history (
    run_id TEXT NOT NULL,
    simulation_day BIGINT NOT NULL,
    event_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    product_id TEXT NOT NULL,
    category TEXT NOT NULL,

    PRIMARY KEY (run_id, event_id)
);


-- =====================================================
-- 6. HISTORICAL CONVERSION DECISIONS
-- =====================================================

CREATE TABLE IF NOT EXISTS staging.conversion_history (
    run_id TEXT NOT NULL,
    simulation_day BIGINT NOT NULL,
    customer_id TEXT NOT NULL,
    result_json JSONB NOT NULL,

    PRIMARY KEY (
        run_id,
        simulation_day,
        customer_id
    ),

    CHECK (jsonb_typeof(result_json) = 'object')
);


-- =====================================================
-- 7. ORIGINAL DAILY METRICS
-- =====================================================

CREATE TABLE IF NOT EXISTS staging.daily_metrics_source (
    run_id TEXT NOT NULL,
    simulation_day BIGINT NOT NULL,
    customers BIGINT NOT NULL,
    behavior_events_json JSONB NOT NULL,
    conversion_json JSONB NOT NULL,
    orders_json JSONB NOT NULL,
    purchase_events BIGINT NOT NULL,

    PRIMARY KEY (run_id, simulation_day)
);


-- =====================================================
-- 8. CLEANED DAILY METRICS
-- =====================================================

CREATE TABLE IF NOT EXISTS staging.daily_metrics_cleaned (
    run_id TEXT NOT NULL,
    simulation_day BIGINT NOT NULL,
    customers BIGINT NOT NULL,
    behavior_event_count BIGINT NOT NULL,
    behavior_active_customers BIGINT NOT NULL,
    conversion_decisions_evaluated BIGINT NOT NULL,
    historical_converted_decisions BIGINT NOT NULL,
    clean_order_count BIGINT NOT NULL,
    clean_purchase_event_count BIGINT NOT NULL,
    clean_event_count BIGINT NOT NULL,

    PRIMARY KEY (run_id, simulation_day)
);


-- =====================================================
-- 9. INGESTION REGISTRY
-- =====================================================

CREATE TABLE IF NOT EXISTS staging.ingestion_registry (
    run_id TEXT NOT NULL,
    dataset_name TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    expected_rows BIGINT NOT NULL,
    loaded_rows BIGINT NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (run_id, dataset_name)
);


-- =====================================================
-- QUERY PERFORMANCE INDEXES
-- =====================================================

CREATE INDEX IF NOT EXISTS idx_staging_orders_day
ON staging.orders (run_id, simulation_day);

CREATE INDEX IF NOT EXISTS idx_staging_events_day
ON staging.events (run_id, simulation_day);

CREATE INDEX IF NOT EXISTS idx_staging_behavior_day
ON staging.behavior_history (run_id, simulation_day);

CREATE INDEX IF NOT EXISTS idx_staging_conversion_day
ON staging.conversion_history (run_id, simulation_day);


COMMIT;


-- =====================================================
-- VALIDATION
-- =====================================================

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'staging'
  AND table_type = 'BASE TABLE'
ORDER BY table_name;

SELECT COUNT(*) AS staging_table_count
FROM information_schema.tables
WHERE table_schema = 'staging'
  AND table_type = 'BASE TABLE';
