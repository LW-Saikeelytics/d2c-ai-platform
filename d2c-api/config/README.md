# M14 API — Configuration Guide

## 1. Configuration Architecture

The M14 API uses two configuration sources:

- JSON files for simulation parameters.
- Environment variables for runtime behavior.

Existing Phase 6, Phase 7, and Phase 8 configurations remain separate.

## 2. Supported Environments

The API recognizes:

- development
- testing
- production

Environment selection:

M14_ENV=development

When M14_ENV is not defined, the application defaults to development.

Production deployments must explicitly set M14_ENV=production.

## 3. Simulation Execution Switch

M14_ENABLE_SIMULATION_START controls whether the API
simulation execution endpoint is enabled.

Supported values:

- 0: Disabled
- 1: Enabled where permitted

The default is 0.

Production execution is rejected even when the flag is 1.

Development and testing environments can enable execution
explicitly. Testing environments should normally keep it disabled.

Invalid environment settings cause the API simulation
endpoint to return HTTP 503.

## 4. Simulation Configuration

The existing SimulationConfig contract supports:

- days
- customers
- scenario
- seed

The current generator supports seed 42 only.

API execution workload limits:

- Maximum days: 30
- Maximum customers: 1000
- Maximum days * customers: 7000

## 5. Example Configurations

config/development_simulation.json

config/examples/festive_peak_demo.json

config/examples/low_inventory_demo.json

Example configurations use registered Phase 6 scenarios
and are validated using the existing Pydantic contract.

## 6. Local Development

From the d2c-api directory, set:

$env:M14_ENV = "development"
$env:M14_ENABLE_SIMULATION_START = "0"

Run the configuration test:

.\.venv\Scripts\python.exe -m src.config.environment_settings_test

Run the API environment gate test:

.\.venv\Scripts\python.exe -m src.api.environment_gate_test

## 7. Security Notes

Never commit real passwords, API keys, or tokens.

Use environment variables or a managed secret store
for credentials.

The simulation execution flag is not authentication.

Production mode currently blocks API simulation execution.
It does not provide authentication or authorization for
other endpoints.

Do not expose the API publicly without additional
security controls and deployment review.

## 8. Backward Compatibility

Phase 6 simulation logic remains unchanged.

Phase 8 warehouse and pipeline behavior remains unchanged.

Phase 9 existing API contracts and regression tests
must continue passing.

Changes to deterministic seed handling are deferred
to Phase 10.3.