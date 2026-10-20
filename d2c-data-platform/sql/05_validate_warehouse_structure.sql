
-- =====================================================
-- PHASE 8.6.2 - WAREHOUSE STRUCTURE VALIDATION
-- =====================================================

\pset pager off

BEGIN;
SET TRANSACTION READ ONLY;

-- =====================================================
-- 1. VERIFY PRIMARY KEYS
-- =====================================================

SELECT
    table_name,
    constraint_name,
    'PASS' AS status
FROM information_schema.table_constraints
WHERE table_schema = 'warehouse'
  AND constraint_type = 'PRIMARY KEY'
ORDER BY table_name;


-- =====================================================
-- 2. VERIFY FOREIGN KEY RELATIONSHIPS
-- =====================================================

SELECT
    child.relname AS fact_table,
    parent.relname AS referenced_table,
    pg_get_constraintdef(c.oid) AS relationship
FROM pg_constraint c

JOIN pg_class child
    ON child.oid = c.conrelid

JOIN pg_class parent
    ON parent.oid = c.confrelid

JOIN pg_namespace n
    ON n.oid = child.relnamespace

WHERE n.nspname = 'warehouse'
  AND c.contype = 'f'

ORDER BY child.relname, parent.relname;


-- =====================================================
-- 3. CHECK THAT WAREHOUSE TABLES ARE EMPTY
-- =====================================================

SELECT 'dim_customers' AS table_name, COUNT(*) AS rows
FROM warehouse.dim_customers

UNION ALL
SELECT 'dim_products', COUNT(*)
FROM warehouse.dim_products

UNION ALL
SELECT 'dim_days', COUNT(*)
FROM warehouse.dim_days

UNION ALL
SELECT 'fact_orders', COUNT(*)
FROM warehouse.fact_orders

UNION ALL
SELECT 'fact_events', COUNT(*)
FROM warehouse.fact_events

UNION ALL
SELECT 'fact_daily_metrics', COUNT(*)
FROM warehouse.fact_daily_metrics;


-- =====================================================
-- 4. AUTOMATED STRUCTURE ASSERTIONS
-- =====================================================

DO $$
DECLARE
    v_tables INTEGER;
    v_primary_keys INTEGER;
    v_foreign_keys INTEGER;
    v_natural_keys INTEGER;
    v_rows BIGINT;

BEGIN

    SELECT COUNT(*)
    INTO v_tables
    FROM information_schema.tables
    WHERE table_schema = 'warehouse'
      AND table_type = 'BASE TABLE';

    SELECT COUNT(*)
    INTO v_primary_keys
    FROM pg_constraint
    WHERE connamespace = 'warehouse'::regnamespace
      AND contype = 'p';

    SELECT COUNT(*)
    INTO v_foreign_keys
    FROM pg_constraint
    WHERE connamespace = 'warehouse'::regnamespace
      AND contype = 'f';

    SELECT COUNT(*)
    INTO v_natural_keys
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    WHERE c.connamespace = 'warehouse'::regnamespace
      AND c.contype = 'u'
      AND t.relname IN (
          'dim_customers',
          'dim_products',
          'dim_days'
      );

    SELECT
        (SELECT COUNT(*) FROM warehouse.dim_customers)
      + (SELECT COUNT(*) FROM warehouse.dim_products)
      + (SELECT COUNT(*) FROM warehouse.dim_days)
      + (SELECT COUNT(*) FROM warehouse.fact_orders)
      + (SELECT COUNT(*) FROM warehouse.fact_events)
      + (SELECT COUNT(*) FROM warehouse.fact_daily_metrics)
    INTO v_rows;

    IF v_tables <> 6 THEN
        RAISE EXCEPTION
            'Expected 6 warehouse tables, found %',
            v_tables;
    END IF;

    IF v_primary_keys <> 6 THEN
        RAISE EXCEPTION
            'Expected 6 primary keys, found %',
            v_primary_keys;
    END IF;

    IF v_foreign_keys <> 8 THEN
        RAISE EXCEPTION
            'Expected 8 foreign keys, found %',
            v_foreign_keys;
    END IF;

    IF v_natural_keys <> 3 THEN
        RAISE EXCEPTION
            'Expected 3 dimension unique keys, found %',
            v_natural_keys;
    END IF;

    IF v_rows <> 0 THEN
        RAISE EXCEPTION
            'Warehouse expected to be empty, found % rows',
            v_rows;
    END IF;

    -- Every expected dimension/fact relationship must exist.

    IF EXISTS (
        SELECT 1
        FROM (
            VALUES
                ('fact_orders', 'dim_customers'),
                ('fact_orders', 'dim_products'),
                ('fact_orders', 'dim_days'),
                ('fact_events', 'dim_customers'),
                ('fact_events', 'dim_products'),
                ('fact_events', 'dim_days'),
                ('fact_events', 'fact_orders'),
                ('fact_daily_metrics', 'dim_days')
        ) AS expected(fact_table, parent_table)

        WHERE NOT EXISTS (
            SELECT 1
            FROM pg_constraint c
            JOIN pg_class child
                ON child.oid = c.conrelid
            JOIN pg_class parent
                ON parent.oid = c.confrelid
            JOIN pg_namespace n
                ON n.oid = child.relnamespace
            WHERE n.nspname = 'warehouse'
              AND c.contype = 'f'
              AND child.relname = expected.fact_table
              AND parent.relname = expected.parent_table
        )
    ) THEN
        RAISE EXCEPTION
            'An expected warehouse relationship is missing';
    END IF;

    -- Composite foreign keys must connect by run_id.

    IF EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class child
            ON child.oid = c.conrelid
        JOIN pg_namespace n
            ON n.oid = child.relnamespace
        JOIN pg_attribute source_column
            ON source_column.attrelid = c.conrelid
           AND source_column.attnum = c.conkey[1]
        JOIN pg_attribute target_column
            ON target_column.attrelid = c.confrelid
           AND target_column.attnum = c.confkey[1]
        WHERE n.nspname = 'warehouse'
          AND c.contype = 'f'
          AND (
              cardinality(c.conkey) <> 2
              OR cardinality(c.confkey) <> 2
              OR source_column.attname <> 'run_id'
              OR target_column.attname <> 'run_id'
          )
    ) THEN
        RAISE EXCEPTION
            'Foreign keys must include matching run_id columns';
    END IF;

    RAISE NOTICE 'Warehouse tables: %', v_tables;
    RAISE NOTICE 'Primary keys: %', v_primary_keys;
    RAISE NOTICE 'Foreign keys: %', v_foreign_keys;
    RAISE NOTICE 'Dimension unique keys: %', v_natural_keys;
    RAISE NOTICE 'Current warehouse rows: %', v_rows;

    RAISE NOTICE
        'WAREHOUSE STRUCTURE VALIDATION PASSED.';

END
$$;

COMMIT;
