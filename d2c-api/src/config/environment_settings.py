
import os

from dataclasses import dataclass
from typing import Mapping


VALID_ENVIRONMENTS = {
    "development",
    "testing",
    "production",
}


@dataclass(frozen=True)
class EnvironmentSettings:
    environment: str
    simulation_start_enabled: bool


def load_environment_settings(
    environ: Mapping[str, str] | None = None
) -> EnvironmentSettings:
    """
    Read and validate M14 API environment settings.

    This does not change process environment variables
    or launch simulations.
    """

    values = os.environ if environ is None else environ

    environment = values.get(
        "M14_ENV",
        "development",
    )

    if environment not in VALID_ENVIRONMENTS:
        raise ValueError(
            "M14_ENV must be development, testing, "
            "or production"
        )

    execution_flag = values.get(
        "M14_ENABLE_SIMULATION_START",
        "0",
    )

    if execution_flag not in {"0", "1"}:
        raise ValueError(
            "M14_ENABLE_SIMULATION_START "
            "must be 0 or 1"
        )

    enabled = execution_flag == "1"

    # Production API execution must remain disabled
    # until authenticated authorization is added.
    if environment == "production" and enabled:
        raise ValueError(
            "API simulation execution cannot be "
            "enabled in production without "
            "an approved security implementation"
        )

    return EnvironmentSettings(
        environment=environment,
        simulation_start_enabled=enabled,
    )
