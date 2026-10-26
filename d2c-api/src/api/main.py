import os

from fastapi import Response
from fastapi import FastAPI, HTTPException
from fastapi import Query
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse

from src.config.scenario_registry import (
    get_supported_scenarios,
)

from typing import Literal

from src.config.scenario_registry import (
    get_supported_scenarios,
)

from src.runtime.run_workspace import (
    RUN_ID_PATTERN,
)

from src.services.run_history_service import (
    get_run_status,
    list_run_history,
)

from src.config.simulation_config import (
    SimulationConfig,
    build_runner_arguments,
)

from src.config.scenario_registry import (
    validate_scenario,
)

from src.api.simulation_start_request import (
    SimulationStartRequest,
)

from src.services.managed_execution import (
    run_managed_simulation,
)

from src.services.execution_lock import (
    SimulationBusyError,
)

from src.runtime.run_workspace import RUN_ID_PATTERN

from src.services.dataset_catalog_service import (
    DatasetNotReadyError,
    list_run_datasets,
)

from src.services.dataset_download_service import (
    DATASET_ID_PATTERN,
    DatasetNotFoundError,
    resolve_dataset_download,
)

from src.services.run_metrics_service import (
    get_run_metrics,
)

from src.services.combined_validation_report_service import (
    get_combined_validation_report,
)

from src.services.scenario_parameters_service import (
    SCENARIO_NAME_PATTERN,
    ScenarioNotFoundError,
    get_scenario_parameters,
)

from src.services.run_history_query_service import (
    get_run_history_page,
)

from src.api.run_history_view import (
    render_run_history_html,
)

app = FastAPI(
    title="M14 D2C AI Platform API",
    description="Simulation management and analytics API",
    version="0.1.0",
)

# Fields safe to expose through read-only endpoints.
# Do not return local filesystem paths or raw errors.

PUBLIC_RUN_FIELDS = (
    "run_id",
    "status",
    "scenario",
    "days",
    "customers",
    "created_at",
    "started_at",
    "finished_at",
    "exit_code",
)


def public_run(record):

    return {
        field: record.get(field)
        for field in PUBLIC_RUN_FIELDS
    }


# =====================================================
# API HEALTH
# =====================================================

@app.get("/health")
def health():

    return {
        "service": "m14-d2c-api",
        "status": "healthy",
        "version": "0.1.0",
    }


# =====================================================
# AVAILABLE SIMULATION SCENARIOS
# =====================================================

@app.get("/api/v1/scenarios")
def get_scenarios():

    scenarios = get_supported_scenarios()

    return {
        "total": len(scenarios),
        "scenarios": list(scenarios.values()),
    }


# =====================================================
# SIMULATION HISTORY
# =====================================================

@app.get("/api/v1/runs")
def get_runs():

    history = list_run_history()

    return {
        "total": len(history),
        "runs": [
            public_run(item)
            for item in history
        ],
    }


# =====================================================
# INDIVIDUAL SIMULATION STATUS
# =====================================================

@app.get("/api/v1/runs/{run_id}")
def get_run(run_id: str):

    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise HTTPException(
            status_code=422,
            detail="Invalid simulation run ID",
        )

    try:
        record = get_run_status(run_id)

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Simulation run not found",
        ) from None

    return public_run(record)


# =====================================================
# PHASE 9.4 - SIMULATION REQUEST VALIDATION
# =====================================================

@app.post("/api/v1/config/validate")
def validate_simulation_request(
    config: SimulationConfig,
):
    """
    Validate simulation parameters without
    executing or reserving a simulation run.
    """

    try:
        scenario = validate_scenario(config)

    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="Unsupported simulation scenario",
        ) from None

    return {
        "valid": True,
        "configuration": config.model_dump(),
        "scenario": scenario,
        "runner_arguments": build_runner_arguments(
            config
        ),
    }


# =====================================================
# PHASE 9.5.4 - START SIMULATION THROUGH API
# =====================================================

@app.post("/api/v1/runs", status_code=201)
def start_simulation(
    request: SimulationStartRequest,
    response: Response,
):
    """
    Start a validated simulation through the
    managed execution service.

    Execution is disabled by default.

    This initial implementation is synchronous:
    the HTTP response is returned after the
    simulation finishes or fails.
    """

    # ---------------------------------------------
    # DEVELOPMENT EXECUTION SWITCH
    # ---------------------------------------------

    if os.environ.get(
        "M14_ENABLE_SIMULATION_START"
    ) != "1":

        raise HTTPException(
            status_code=503,
            detail="Simulation execution is disabled",
        )

    # ---------------------------------------------
    # VALIDATED CONFIGURATION
    # ---------------------------------------------

    config = request.to_simulation_config()

    # ---------------------------------------------
    # MANAGED EXECUTION
    # ---------------------------------------------

    try:

        record, workspace = run_managed_simulation(
            config
        )

    except SimulationBusyError:

        raise HTTPException(
            status_code=409,
            detail="Another simulation is already active",
        ) from None

    except (RuntimeError, OSError):

        raise HTTPException(
            status_code=503,
            detail=(
                "Simulation execution unavailable; "
                "inspect the local runtime logs"
            ),
        ) from None

    # ---------------------------------------------
    # RETURN PUBLIC EXECUTION RESULT
    # ---------------------------------------------

    response.headers["Location"] = (
        f"/api/v1/runs/{record['run_id']}"
    )

    return public_run(record)


# =====================================================
# PHASE 9.7.3 - GET SIMULATION DATASET CATALOG
# =====================================================

@app.get("/api/v1/runs/{run_id}/datasets")
def get_simulation_datasets(run_id: str):

    # ---------------------------------------------
    # VALIDATE RUN IDENTIFIER
    # ---------------------------------------------

    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise HTTPException(
            status_code=422,
            detail="Invalid simulation run ID",
        )

    # ---------------------------------------------
    # READ DATASET CATALOG
    # ---------------------------------------------

    try:

        catalog = list_run_datasets(run_id)

    except FileNotFoundError:

        raise HTTPException(
            status_code=404,
            detail="Simulation run not found",
        ) from None

    except DatasetNotReadyError:

        raise HTTPException(
            status_code=409,
            detail="Simulation datasets are not ready",
        ) from None

    except (RuntimeError, OSError, ValueError, TypeError):

        raise HTTPException(
            status_code=500,
            detail="Dataset catalog unavailable",
        ) from None

    # ---------------------------------------------
    # RETURN PUBLIC DATASET METADATA
    # ---------------------------------------------

    return catalog


# =====================================================
# PHASE 9.7.4B - HTTP DATASET DOWNLOAD ENDPOINT
# =====================================================

@app.get(
    "/api/v1/runs/{run_id}/datasets/{dataset_id}",
    response_class=FileResponse,
)
def download_simulation_dataset(
    run_id: str,
    dataset_id: str,
):

    # ---------------------------------------------
    # VALIDATE IDENTIFIERS
    # ---------------------------------------------

    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise HTTPException(
            status_code=422,
            detail="Invalid simulation run ID",
        )

    if not DATASET_ID_PATTERN.fullmatch(dataset_id):
        raise HTTPException(
            status_code=422,
            detail="Invalid dataset identifier",
        )

    # ---------------------------------------------
    # RESOLVE APPROVED DATASET
    # ---------------------------------------------

    try:

        dataset = resolve_dataset_download(
            run_id,
            dataset_id,
        )

    except DatasetNotFoundError:

        raise HTTPException(
            status_code=404,
            detail="Dataset not found",
        ) from None

    except FileNotFoundError:

        raise HTTPException(
            status_code=404,
            detail="Simulation run not found",
        ) from None

    except DatasetNotReadyError:

        raise HTTPException(
            status_code=409,
            detail="Simulation datasets are not ready",
        ) from None

    except (RuntimeError, OSError, ValueError, TypeError):

        raise HTTPException(
            status_code=500,
            detail="Dataset file unavailable",
        ) from None

    # ---------------------------------------------
    # SEND FILE AS DOWNLOADABLE ATTACHMENT
    # ---------------------------------------------

    return FileResponse(
        path=dataset["file_path"],
        media_type=dataset["media_type"],
        filename=dataset["filename"],
        content_disposition_type="attachment",
    )


# =====================================================
# PHASE 9.8.3 - BUSINESS METRICS API
# =====================================================

@app.get("/api/v1/runs/{run_id}/metrics")
def get_simulation_metrics(run_id: str):

    """
    Retrieve structured business metrics from
    a completed simulation.

    Includes:
    - Business KPI summary
    - Shopping funnel metrics
    - Daily, weekly and monthly trends

    Read-only. Does not execute simulations.
    """

    # ---------------------------------------------
    # VALIDATE RUN IDENTIFIER
    # ---------------------------------------------

    if not RUN_ID_PATTERN.fullmatch(run_id):

        raise HTTPException(
            status_code=422,
            detail="Invalid simulation run ID",
        )

    # ---------------------------------------------
    # RETRIEVE BUSINESS METRICS
    # ---------------------------------------------

    try:

        metrics = get_run_metrics(run_id)

    except FileNotFoundError:

        raise HTTPException(
            status_code=404,
            detail="Simulation run not found",
        ) from None

    except DatasetNotReadyError:

        raise HTTPException(
            status_code=409,
            detail=(
                "Business metrics are available "
                "only for completed simulations"
            ),
        ) from None

    except (
        RuntimeError,
        LookupError,
        OSError,
        ValueError,
        TypeError,
    ):

        raise HTTPException(
            status_code=500,
            detail="Business metrics unavailable",
        ) from None

    # ---------------------------------------------
    # RETURN STRUCTURED METRICS
    # ---------------------------------------------

    return metrics


# =====================================================
# PHASE 9.9.3 - VALIDATION RESULTS API
# =====================================================

@app.get("/api/v1/runs/{run_id}/validations")
def get_simulation_validations(run_id: str):

    """
    Retrieve validation evidence for a completed
    simulation.

    Includes:
    - 8 recorded Phase 6 generator validations
    - 6 Phase 9 cross-manifest consistency checks
    - Combined validation summary
    - Dataset metadata and evidence provenance

    Read-only. Does not rerun Phase 6 validations.
    """

    # ---------------------------------------------
    # VALIDATE RUN IDENTIFIER
    # ---------------------------------------------

    if not RUN_ID_PATTERN.fullmatch(run_id):

        raise HTTPException(
            status_code=422,
            detail="Invalid simulation run ID",
        )

    # ---------------------------------------------
    # RETRIEVE COMBINED VALIDATION REPORT
    # ---------------------------------------------

    try:

        report = get_combined_validation_report(
            run_id
        )

    except FileNotFoundError:

        raise HTTPException(
            status_code=404,
            detail="Simulation run not found",
        ) from None

    except DatasetNotReadyError:

        raise HTTPException(
            status_code=409,
            detail=(
                "Validation results are available "
                "only for completed simulations"
            ),
        ) from None

    except (
        RuntimeError,
        LookupError,
        OSError,
        ValueError,
        TypeError,
    ):

        raise HTTPException(
            status_code=500,
            detail="Validation report unavailable",
        ) from None

    # ---------------------------------------------
    # RETURN PUBLIC VALIDATION REPORT
    # ---------------------------------------------

    return report


# =====================================================
# PHASE 9.10.3 - SCENARIO PARAMETERS API
# =====================================================

@app.get("/api/v1/scenarios/{scenario_name}")
def get_scenario_details(scenario_name: str):

    """
    Retrieve the original Phase 6 scenario
    definition and its configured overrides.

    Read-only:
    - No simulation execution
    - No scenario modification
    - No configuration duplication
    """

    # ==========================================
    # VALIDATE SCENARIO IDENTIFIER
    # ==========================================

    if not SCENARIO_NAME_PATTERN.fullmatch(
        scenario_name
    ):

        raise HTTPException(
            status_code=422,
            detail="Invalid scenario identifier",
        )

    # ==========================================
    # RETRIEVE SCENARIO PARAMETERS
    # ==========================================

    try:

        scenario = get_scenario_parameters(
            scenario_name
        )

    except ScenarioNotFoundError:

        raise HTTPException(
            status_code=404,
            detail="Simulation scenario not found",
        ) from None

    except (
        FileNotFoundError,
        OSError,
        ValueError,
        RuntimeError,
    ):

        raise HTTPException(
            status_code=503,
            detail="Scenario configuration unavailable",
        ) from None

    # ==========================================
    # RETURN PUBLIC SCENARIO DEFINITION
    # ==========================================

    return scenario


# =====================================================
# PHASE 9.11.3B - RUN HISTORY QUERY API
# =====================================================

@app.get("/api/v1/run-history")
def get_simulation_run_history(
    status: str | None = None,
    scenario: str | None = None,
    sort_by: Literal[
        "run_id",
        "created_at",
        "started_at",
        "finished_at",
        "duration_seconds",
    ] = "started_at",
    order: Literal["asc", "desc"] = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """
    Retrieve filtered, sorted and paginated
    simulation history.

    Read-only:
    - No simulation execution
    - No changes to stored run records
    - No private filesystem paths
    """

    try:

        history = get_run_history_page(
            status=status,
            scenario=scenario,
            sort_by=sort_by,
            order=order,
            page=page,
            page_size=page_size,
        )

    except ValueError:

        raise HTTPException(
            status_code=422,
            detail="Invalid run-history query parameters",
        ) from None

    except (RuntimeError, OSError, TypeError):

        raise HTTPException(
            status_code=500,
            detail="Run history unavailable",
        ) from None

    return history


# =====================================================
# PHASE 9.11.4B - BROWSER RUN-HISTORY VIEW
# =====================================================

@app.get(
    "/run-history",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def view_simulation_run_history(
    status: str | None = None,
    scenario: str | None = None,
    sort_by: Literal[
        "run_id",
        "created_at",
        "started_at",
        "finished_at",
        "duration_seconds",
    ] = "started_at",
    order: Literal["asc", "desc"] = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """
    Read-only browser interface for simulation history.

    Uses the existing:
    - Enhanced history service
    - History filtering and pagination
    - HTML history renderer

    No simulation execution or record modification.
    """

    # ==========================================
    # RETRIEVE FILTERED HISTORY
    # ==========================================

    try:

        history = get_run_history_page(
            status=status,
            scenario=scenario,
            sort_by=sort_by,
            order=order,
            page=page,
            page_size=page_size,
        )

    except ValueError:

        raise HTTPException(
            status_code=422,
            detail="Invalid run-history query parameters",
        ) from None

    except (RuntimeError, OSError, TypeError):

        raise HTTPException(
            status_code=500,
            detail="Run history unavailable",
        ) from None

    # ==========================================
    # RENDER READ-ONLY HTML VIEW
    # ==========================================

    try:

        scenarios = get_supported_scenarios()

        html = render_run_history_html(
            history,
            scenarios,
        )

    except (ValueError, RuntimeError, OSError, TypeError):

        raise HTTPException(
            status_code=500,
            detail="Run-history view unavailable",
        ) from None

    # ==========================================
    # RETURN HTML WITH SECURITY HEADERS
    # ==========================================

    return HTMLResponse(
        content=html,
        status_code=200,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Content-Security-Policy": (
                "default-src 'none'; "
                "style-src 'unsafe-inline'; "
                "form-action 'self'; "
                "base-uri 'none'; "
                "frame-ancestors 'none'"
            ),
        },
    )
