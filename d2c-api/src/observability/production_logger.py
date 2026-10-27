
import json
import logging
import re

from datetime import datetime, timezone
from typing import TextIO


VALID_LEVELS = {
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
}

SAFE_IDENTIFIER = re.compile(
    r"^[A-Za-z][A-Za-z0-9_]{0,63}$"
)

SAFE_EXECUTION_ID = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"
)


class JsonEventFormatter(logging.Formatter):
    """
    Convert a diagnostic event to a JSONL record.

    Raw exception messages and tracebacks are
    deliberately excluded.
    """

    def format(self, record):

        payload = {
            "timestamp_utc": datetime.fromtimestamp(
                record.created,
                timezone.utc,
            ).isoformat(),

            "level": record.levelname,
            "component": record.component,
            "event": record.event,
            "execution_id": record.execution_id,
            "error_type": record.error_type,
        }

        return json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
        )


class ProductionLogger:
    """
    Isolated structured application logger.

    Does not configure the global root logger.
    Does not create application log files.
    """

    def __init__(
        self,
        component: str,
        minimum_level: str = "INFO",
        stream: TextIO | None = None,
    ):

        if not isinstance(component, str) or not (
            SAFE_IDENTIFIER.fullmatch(component)
        ):
            raise ValueError(
                "Invalid logging component"
            )

        if minimum_level not in VALID_LEVELS:
            raise ValueError(
                "Unsupported logging level"
            )

        self.component = component

        # A standalone logger avoids modifying the
        # application's global logging configuration.
        self._logger = logging.Logger(
            name=f"m14.{component}",
            level=getattr(
                logging,
                minimum_level,
            ),
        )

        self._logger.propagate = False

        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonEventFormatter())

        self._logger.addHandler(handler)

    def log_event(
        self,
        level: str,
        event: str,
        execution_id: str | None = None,
        error: BaseException | None = None,
    ):
        """
        Log a structured diagnostic event.

        Only event identifiers and exception types
        are recorded. No arbitrary message payloads.
        """

        if level not in VALID_LEVELS:
            raise ValueError(
                "Unsupported event logging level"
            )

        if not isinstance(event, str) or not (
            SAFE_IDENTIFIER.fullmatch(event)
        ):
            raise ValueError(
                "Invalid logging event"
            )

        if execution_id is not None:
            if not isinstance(execution_id, str) or not (
                SAFE_EXECUTION_ID.fullmatch(execution_id)
            ):
                raise ValueError(
                    "Invalid execution identifier"
                )

        if error is not None and not isinstance(
            error,
            BaseException,
        ):
            raise TypeError(
                "error must be an exception"
            )

        error_type = (
            type(error).__name__
            if error is not None
            else None
        )

        self._logger.log(
            getattr(logging, level),
            event,
            extra={
                "component": self.component,
                "event": event,
                "execution_id": execution_id,
                "error_type": error_type,
            },
        )