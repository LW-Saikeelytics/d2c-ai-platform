
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from src.config.simulation_config import (
    SimulationConfig,
)

from src.config.scenario_registry import (
    validate_scenario,
)


# =====================================================
# PHASE 9.5.1 - API SIMULATION EXECUTION LIMITS
# =====================================================

MAX_DAYS = 30
MAX_CUSTOMERS = 1000
MAX_WORK_UNITS = 7000


class SimulationStartRequest(BaseModel):

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    # Explicit values are required for API launches.
    # We do not silently use the generator's
    # 90-day / 10,000-customer defaults.

    days: int = Field(
        ...,
        strict=True,
        ge=1,
        le=MAX_DAYS,
    )

    customers: int = Field(
        ...,
        strict=True,
        ge=1,
        le=MAX_CUSTOMERS,
    )

    scenario: str = Field(
        ...,
        strict=True,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
    )

    # Phase 6 currently supports a fixed seed.
    seed: Literal[42]

    # =================================================
    # COMBINED WORKLOAD AND SCENARIO VALIDATION
    # =================================================

    @model_validator(mode="after")
    def validate_execution_limits(self):

        work_units = self.days * self.customers

        if work_units > MAX_WORK_UNITS:
            raise ValueError(
                "Simulation workload exceeds the "
                f"development limit of {MAX_WORK_UNITS} "
                "day-customer units"
            )

        # Validate the scenario against the existing
        # Phase 6 registry, not a duplicate list.

        validate_scenario(
            self.to_simulation_config()
        )

        return self

    # =================================================
    # REUSE EXISTING SIMULATION CONFIG CONTRACT
    # =================================================

    def to_simulation_config(self):

        return SimulationConfig.model_validate(
            self.model_dump()
        )