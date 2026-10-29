# M14 — D2C AI Platform

A portfolio-scale Python platform for simulating direct-to-consumer
business activity, generating synthetic datasets, developing ML
intelligence, engineering analytics pipelines, and serving business
insights through APIs and a PostgreSQL warehouse.

## Platform modules

| Module | Purpose |
|---|---|
| d2c-synthetic-data | Customer, event, behavior, conversion and order simulation |
| d2c-ml-intelligence | Customer segmentation, churn, propensity, CLV and recommendations |
| d2c-data-platform | Raw, processed, analytics and Parquet layers; PostgreSQL warehouse |
| d2c-api | FastAPI services for simulation management, metrics, history and datasets |

## Architecture

See [Architecture](docs/architecture.md).

The platform separates synthetic data generation, ML evaluation,
data engineering and API delivery.

## Frozen dataset

Production reference run:

`simulation_run_20261004_120957`

| Metric | Recorded value |
|---|---:|
| Simulation days | 90 |
| Customers | 10,000 |
| Raw orders | 2,915 |
| Raw events | 96,632 |
| Clean orders | 2,913 |
| Clean events | 96,508 |
| Reconciled warehouse revenue | 53,812,160.00 |

The cleaned warehouse excludes two orders for product PRD-MAT-006
placed before its launch on simulation day 6.

An additional 124 raw events are absent from the processed event
dataset. These exclusions are preserved in the raw-to-clean
data-quality reconciliation.

## Performance evidence

A historical 90-day, 10,000-customer simulation recorded:

- Simulation execution time: 43.4279 seconds
- Peak Python-tracked memory: 56.54 MB
- Calculated throughput: approximately 20,724 customer-days/second

This is a single historical benchmark of simulation execution,
not a full end-to-end pipeline or concurrent load benchmark.

## Validation

- Deterministic seed configuration and source hashes verified
- Frozen data-platform output fingerprint verified
- 28 of 28 discovered API regression modules passed
- Warehouse staging, facts and daily business metrics reconciled
- Historical datasets preserved during production-engineering checks

## Installation

Each module has its own `requirements.txt`.

For Windows setup instructions, environment creation,
database configuration and safe verification commands,
see the [Developer Guide](docs/developer_guide.md).

Exact package versions and fresh-machine compatibility
have not yet been independently verified.
## Configuration

Existing example scenarios:

- `d2c-api/config/development_simulation.json`
- `d2c-api/config/examples/festive_peak_demo.json`
- `d2c-api/config/examples/low_inventory_demo.json`

Additional business master data and scenario configurations
are available inside `d2c-synthetic-data/config`.

## Developer documentation

- [Developer guide](docs/developer_guide.md)
- [Architecture](docs/architecture.md)
- [Data platform README](d2c-data-platform/README.md)
- [API configuration](d2c-api/config/README.md)
- [Production logging](d2c-api/docs/production_logging.md)

## Roadmap

- Production engineering: final documentation and verification
- BI layer: Power BI/Tableau dashboards and business use cases
- Deployment: containerization, delivery automation and portfolio completion

## Operational safety

Frozen datasets and historical ML outputs are reference artifacts.
Validation and inspection should not regenerate or overwrite them.

Live simulations, model training and ETL workflows must be run
only with deliberate configuration and appropriate isolation.
