
# D2C Data Engineering Platform

## Overview

A production-style Data Engineering and Analytics Platform
built for the DreamNest Living synthetic D2C business.

This module transforms validated synthetic commerce data
into structured analytical datasets using Python, Parquet,
PostgreSQL, and dimensional data modeling.

It is Phase 8 of the larger M14 D2C AI Platform project.

## Architecture

Synthetic Data Generator (Phase 6)
          |
          v
      Raw Layer
          |
          v
    Processed Layer
          |
          v
     Analytics Layer
          |
          v
   Partitioned Parquet
          |
          v
   PostgreSQL Staging
          |
          v
  Dimensional Warehouse
          |
          v
 SQL Analytics & Reporting

The platform includes orchestration, structured logging,
data validation, reproducibility checks, and integration audits.

## Technology Stack

| Component | Technology |
|---|---|
| Programming | Python 3.11 |
| Columnar storage | Apache Parquet / PyArrow |
| Database | PostgreSQL 18 |
| Database driver | psycopg 3 |
| Analytical modeling | SQL / Star Schema |
| Pipeline orchestration | Python |
| Execution logging | JSONL |
| Reproducibility | SHA-256 / Seed Provenance |
| Version control | Git / GitHub |

## Source Dataset

The platform processes a frozen 90-day synthetic simulation.

| Metric | Validated Value |
|---|---:|
| Customers | 10,000 |
| Products | 29 |
| Simulation days | 90 |
| Valid orders | 2,913 |
| Units sold | 3,340 |
| Behavioral events | 93,595 |
| Total events | 96,508 |
| Conversion evaluations | 53,833 |
| Historical conversions | 2,915 |
| Gross revenue | INR 53,812,160.00 |

Source simulation:

`simulation_run_20261004_120957`

The processing layer removes identified prelaunch
transactions and events without changing the frozen source.

Historical conversion decisions are preserved separately
from validated purchases.

## Data Architecture

### Raw Layer

- Preserves frozen source files
- Uses SHA-256 validation
- Supports safe reruns
- Maintains source manifests

### Processed Layer

- Standardizes transactional and entity data
- Cleans invalid prelaunch activity
- Reconciles customer lifetime metrics
- Preserves historical conversion decisions
- Validates customer, product, and order relationships

### Analytics Layer

- Generates daily business metrics
- Generates product performance metrics
- Reconciles revenue and transaction counts

### Parquet Storage

- Compressed columnar datasets
- Run-scoped storage
- Simulation-day partitioning
- Hive-style event and transaction partitions
- 366 validated Parquet data files

## PostgreSQL Staging

Eight business datasets are ingested into PostgreSQL:

| Table | Records |
|---|---:|
| customers | 10,000 |
| product_master | 29 |
| orders | 2,913 |
| events | 96,508 |
| behavior_history | 93,595 |
| conversion_history | 53,833 |
| daily_metrics_source | 90 |
| daily_metrics_cleaned | 90 |

Total: 257,058 business records.

The staging schema also includes an ingestion registry
for tracking dataset loads, source fingerprints, and counts.

Existing validated datasets are safely reused on reruns.

## Dimensional Warehouse

The analytical warehouse uses a star-schema design.

### Dimensions

- `warehouse.dim_customers`
- `warehouse.dim_products`
- `warehouse.dim_days`

### Facts

- `warehouse.fact_orders`
- `warehouse.fact_events`
- `warehouse.fact_daily_metrics`

Surrogate keys connect facts to dimensions.

Composite relationships include the simulation `run_id`
to prevent records from different runs being mixed.

Customer attributes represent an end-of-run snapshot.
Simulation days are not assumed to be calendar dates.

## Pipeline Orchestration

The platform contains ten ETL/ELT stages:

1. raw_ingestion
2. processed_transactions
3. processed_entities
4. processed_activity
5. analytics_layer
6. analytics_parquet
7. events_parquet
8. transactions_parquet
9. core_parquet
10. integrity_audit

Pipeline stages execute in dependency order.

The orchestrator supports:

- Dry-run execution plans
- Existing-output reuse
- Manifest verification
- Dependency checking
- Controlled failure propagation
- Final Parquet integrity auditing

## Running the Platform

Run the following commands from the
`d2c-data-platform` directory.

The project requires an appropriately configured
Python environment, access to the frozen source data,
and a local PostgreSQL database.

### Dry Run

```powershell
& ".\.venv\Scripts\python.exe" -m src.pipelines.run_with_logging
```

### Execute the Pipeline

```powershell
& ".\.venv\Scripts\python.exe" -m src.pipelines.run_with_logging --run
```

### Ingest Parquet into PostgreSQL

```powershell
& ".\.venv\Scripts\python.exe" -m src.database.parquet_ingestion
```

PostgreSQL credentials are requested interactively.

### Run the Full Platform Audit

```powershell
& ".\.venv\Scripts\python.exe" -m src.pipelines.full_platform_audit
```

This performs file, fingerprint, execution-log,
database, and warehouse validations.

It requires the previously generated platform outputs
and configured PostgreSQL tables.

## Validation

The completed platform has passed:

| Validation | Result |
|---|---|
| File pipeline stages | 10/10 |
| Execution log records | 22/22 |
| Tracked output files | 411 |
| Parquet files | 366 |
| PostgreSQL staging checks | 18/18 |
| Referential integrity checks | 18/18 |
| Warehouse table checks | 6/6 |
| Warehouse source parity checks | 5/5 |
| Daily reconciliations | 90/90 |
| Cross-layer row checks | 9/9 |
| Cross-layer revenue checks | 4/4 |

The latest full-platform audit status is PASSED.

## Reproducibility

The platform provides:

- Immutable input fingerprints
- Output file SHA-256 fingerprints
- Seed provenance validation
- Generator source-file fingerprinting
- Input and configuration change detection
- Output modification, addition, and deletion detection
- Repeatable reuse-and-audit pipeline execution

The original synthetic generator primarily uses
random seed 42.

The customer profile random stream uses seed 143.

The Order Engine uses a hardcoded seed of 42.

### Reproducibility Scope

The platform has demonstrated byte-for-byte stability
of existing outputs across safe reruns.

A complete fresh rebuild and byte-identical
regeneration of the original synthetic dataset
have not been demonstrated.

## Pipeline Logging

Execution metadata is recorded in structured JSONL:

`logs/pipeline_runs.jsonl`

Each log record contains:

- UTC timestamp
- Source run ID
- Pipeline execution ID
- Stage name
- Execution status
- Duration
- Error type, where applicable

Runtime logs are excluded from Git.

## Audit Reports

Validation artifacts are saved under `reports/`.

Key reports:

- `source_schema_profile.json`
- `parquet_integrity_report.json`
- `reproducibility_baseline.json`
- `seed_provenance.json`
- `pipeline_output_baseline.json`
- `full_platform_audit.json`

## Security

Database passwords are not stored in source configuration
or runtime log records.

Generated runtime logs are excluded from version control.

Source data is kept separate from processed and
analytical outputs.

## Project Status

Phase 8 — Data Engineering / Platform Layer

Technical implementation: COMPLETE

End-to-end platform audit: PASSED

The platform provides a validated data foundation
for downstream analytics, machine learning,
and AI-driven business intelligence.