# M14 — Developer Guide

## Prerequisites

- Python and Git
- Windows PowerShell for the commands below
- Module-specific Python dependencies
- PostgreSQL for database-backed warehouse checks

Open a terminal at the repository root before proceeding.

Use the existing module environments where available.
Do not commit credentials, private environment files,
or generated datasets.

## Repository organization

- `d2c-synthetic-data/`: simulation engine and frozen dataset
- `d2c-ml-intelligence/`: ML baselines and evaluation
- `d2c-data-platform/`: pipelines, Parquet and SQL warehouse
- `d2c-api/`: FastAPI application and regression tests

Each module should be treated as its own Python execution
context when using `python -m`.

## Configuration references

API environment/configuration guidance:

`d2c-api/config/README.md`

Sample API configurations:

- `d2c-api/config/development_simulation.json`
- `d2c-api/config/examples/festive_peak_demo.json`
- `d2c-api/config/examples/low_inventory_demo.json`

Data-platform configuration:

- `d2c-data-platform/config/platform_config.json`
- `d2c-data-platform/config/database_config.json`

Use appropriate local database credentials.
Do not paste secrets into documentation.

## Safe read-only verification commands

The following commands have been used with the existing
frozen M14 artifacts.

### Verify seed provenance

From `d2c-data-platform`:

```powershell
python -B -m src.pipelines.seed_provenance
```

The frozen seed provenance report must already exist.
Do not use this command to initialize a new baseline
without explicitly reviewing its behavior.

### Verify frozen output fingerprint

From `d2c-data-platform`:

```powershell
python -B -m src.pipelines.output_reproducibility --verify
```

This verifies the existing output baseline.
Do not substitute `--capture` on the frozen dataset.

### Run the API smoke test

From `d2c-api`:

```powershell
.\.venv\Scripts\python.exe -B -m src.api.api_smoke_test
```

Requires the existing API virtual environment and its
dependencies. Keep simulation execution disabled.

### Inspect Git state

From the repository root:

```powershell
git status --short
```

## Database read-only inspection

Use the existing Phase 8 PostgreSQL connection.

The dimensional warehouse uses these tables:

- `warehouse.dim_customers`
- `warehouse.dim_products`
- `warehouse.dim_days`
- `warehouse.fact_orders`
- `warehouse.fact_events`
- `warehouse.fact_daily_metrics`

For the frozen reference run, the clean business baseline is
2,913 orders and 96,508 events.

Existing SQL validation definitions are in
`d2c-data-platform/sql/`.

Some SQL files contain schema creation or loading commands.
Do not execute them merely to inspect the database.

## Commands requiring explicit caution

These modules can execute substantial workflows:

- `simulation.production_dataset_runner`
- `simulation.scale_validation`
- `src.baseline_experiment_runner`
- `src.pipelines.pipeline_runner`
- `src.database.parquet_ingestion`

Do not run these against frozen artifacts as routine tests.

## Current test evidence

The 28 discovered API test modules passed in the existing
development environment.

That result is a historical regression record, not
a guarantee for a different dependency environment.

See `d2c-api/docs/production_logging.md` for observability
behavior and exception handling.

## Fresh machine setup (Windows PowerShell)

### 1. Prerequisites

Install and configure:

- Python 3.10 or later
- Git
- PostgreSQL for warehouse-backed functionality
- Access to the M14 repository

Use a supported Python version for all dependencies.
PostgreSQL database provisioning and credentials must be
configured separately using the existing Phase 8 guidance.

### 2. Clone the repository

```powershell
git clone https://github.com/LW-Saikeelytics/d2c-ai-platform.git
cd d2c-ai-platform
```

### 3. Create module environments

From the repository root:

```powershell
$modules = @(
    "d2c-synthetic-data",
    "d2c-ml-intelligence",
    "d2c-data-platform",
    "d2c-api"
)

foreach ($module in $modules) {

    $venv = Join-Path $module ".venv"

    python -m venv $venv

    if ($LASTEXITCODE -ne 0) {
        throw "Environment creation failed: $module"
    }

    $python = Join-Path $venv "Scripts\python.exe"

    & $python -m pip install -r (
        Join-Path $module "requirements.txt"
    )

    if ($LASTEXITCODE -ne 0) {
        throw "Dependency installation failed: $module"
    }
}
```

Each module has its own environment.

The synthetic-data requirements file contains no third-party
packages because none were identified in the source audit.

### 4. Configure the application

Review:

- `d2c-api/config/README.md`
- `d2c-api/config/development_simulation.json`
- `d2c-data-platform/config/platform_config.json`
- `d2c-data-platform/config/database_config.json`

Configure PostgreSQL locally before attempting database
integration or warehouse operations.

Do not commit database credentials or local secrets.

### 5. Verify the API environment

From the repository root:

```powershell
cd d2c-api

.\.venv\Scripts\python.exe -B -m src.api.api_smoke_test

cd ..
```

This smoke test uses existing application data and should be
executed with simulation execution disabled.

### 6. Verify frozen data-platform artifacts

The existing reports must be present before verification.

```powershell
cd d2c-data-platform

.\.venv\Scripts\python.exe -B -m src.pipelines.seed_provenance

.\.venv\Scripts\python.exe -B -m src.pipelines.output_reproducibility --verify

cd ..
```

These commands check existing seed provenance and output
fingerprints. They do not regenerate production data.

### 7. Dependency reproducibility limitations

The requirements files list directly observed dependencies.

Exact dependency versions are not yet locked, and a complete
fresh-machine installation has not been independently tested.

A clean-environment verification and version-locking process
should be completed before production deployment.

Do not run generator, model-training or ETL workflows
against frozen reference artifacts merely to test setup.
