# M14 — Production Logging and Error Management

## 1. Overview

Phase 10.2 introduces structured application logging
and controlled exception reporting.

The implementation preserves the existing Phase 8
pipeline lifecycle logger.

## 2. Logging Architecture

M14 currently has three logging components.

### PipelineLogger

Location:
d2c-data-platform/src/pipelines/pipeline_logger.py

Responsibilities:
- Pipeline lifecycle events
- Source run identification
- Execution ID tracking
- Stage duration recording
- Failure type recording
- JSONL pipeline log output

Supported statuses:
STARTED, SUCCEEDED, FAILED, REUSED, SKIPPED

Existing pipeline behavior remains unchanged.

### ProductionLogger

Location:
d2c-api/src/observability/production_logger.py

Responsibilities:
- Structured application diagnostic events
- UTC timestamps
- Severity levels
- Component identification
- Optional execution identifiers
- Exception type recording

Supported levels:
DEBUG, INFO, WARNING, ERROR

Output:
JSONL events written to standard error by default.

The logger does not configure the global root logger
or create application log files.

### Job Logging Boundary

Location:
d2c-api/src/observability/job_boundary.py

Responsibilities:
- Job lifecycle event logging
- Mocked process execution testing
- Return-code preservation
- Exception propagation

Supported job labels:
generator, ml

Live execution without an injected runner is blocked.

This helper is not a secure command authorization
boundary. Injected runners may perform real actions.

No production generator or ML execution CLI has
been enabled by Phase 10.2.

## 3. Diagnostic Event Format

ProductionLogger emits JSON records containing:

- timestamp_utc
- level
- component
- event
- execution_id
- error_type

The current logging contract records event identifiers
and exception types instead of arbitrary free-text
exception messages.

## 4. FastAPI Exception Logging

The simulation start endpoint records:

SimulationBusyError:
- WARNING
- simulation_execution_busy
- HTTP 409 remains unchanged

RuntimeError or OSError:
- ERROR
- simulation_execution_failed
- HTTP 503 remains unchanged

Exception messages are excluded from these structured
diagnostic events.

Existing public HTTP error messages remain unchanged.

## 5. Safety Requirements

- Do not log passwords, tokens or API keys.
- Do not log sensitive customer data.
- Do not expose raw exception messages to API clients.
- Do not enable generator or ML execution during
  logging tests.
- Do not alter frozen simulation outputs or manifests.
- Do not use arbitrary subprocess commands from
  untrusted requests.

The current implementation does not constitute
a complete secret-redaction system.

## 6. Testing

From the d2c-api directory:

.\.venv\Scripts\python.exe -B -m src.observability.production_logger_test

.\.venv\Scripts\python.exe -B -m src.observability.job_boundary_test

.\.venv\Scripts\python.exe -B -m src.api.simulation_exception_logging_test

The job boundary tests use mocked subprocess runners.

The API exception tests use mocked managed execution.

## 7. Current Coverage

Implemented:
- Phase 8 pipeline lifecycle logging
- Structured production diagnostic logger
- FastAPI simulation exception logging
- Independently tested generator/ML job boundary
- Non-executing boundary defaults
- Failure propagation testing

Not yet implemented:
- Automatic generator runtime logging integration
- Automatic ML workflow logging integration
- Production generator/ML execution CLI
- Centralized platform-wide log collection
- Persistent application log rotation and retention
- Full secret-redaction and sensitive-data auditing
- Comprehensive API request logging and tracing

## 8. Future Work

Phase 10.4:
- Expand logging and exception regression coverage

Phase 10.7:
- Document and validate safe operational CLI commands

Phase 12:
- Deployment logging
- Centralized monitoring
- Log retention
- Production access controls
- Operational alerting

## 9. Backward Compatibility

Phase 6 simulation logic remains unchanged.

Phase 7 ML algorithms remain unchanged.

Phase 8 pipeline logging behavior remains unchanged.

Phase 9 API response contracts remain unchanged.

The Phase 10.2 implementation must pass the full
regression suite before Git freeze.