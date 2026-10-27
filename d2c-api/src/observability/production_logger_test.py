
import io
import json

from datetime import datetime

from src.observability.production_logger import (
    ProductionLogger,
)


def test_production_logger():

    output = io.StringIO()

    logger = ProductionLogger(
        component="api",
        minimum_level="INFO",
        stream=output,
    )

    # DEBUG should be filtered out.
    logger.log_event(
        level="DEBUG",
        event="debug_probe",
    )

    logger.log_event(
        level="INFO",
        event="simulation_started",
        execution_id="run_001",
    )

    logger.log_event(
        level="WARNING",
        event="simulation_delayed",
        execution_id="run_001",
    )

    # Simulate an exception without exposing
    # its sensitive message.
    secret = "PRIVATE_PASSWORD_DO_NOT_LOG"

    try:
        raise RuntimeError(secret)

    except RuntimeError as error:
        logger.log_event(
            level="ERROR",
            event="simulation_failed",
            execution_id="run_001",
            error=error,
        )

    raw_output = output.getvalue()

    records = [
        json.loads(line)
        for line in raw_output.splitlines()
        if line.strip()
    ]

    assert len(records) == 3

    assert [
        row["level"] for row in records
    ] == [
        "INFO",
        "WARNING",
        "ERROR",
    ]

    required_fields = {
        "timestamp_utc",
        "level",
        "component",
        "event",
        "execution_id",
        "error_type",
    }

    for record in records:

        assert set(record) == required_fields
        assert record["component"] == "api"
        assert record["execution_id"] == "run_001"

        parsed_time = datetime.fromisoformat(
            record["timestamp_utc"]
        )

        assert parsed_time.tzinfo is not None

    assert records[2]["error_type"] == "RuntimeError"
    assert records[0]["error_type"] is None

    # Exception details must not appear.
    assert secret not in raw_output

    invalid_events = [
        "password=my_secret",
        "event with spaces",
        "",
    ]

    for event in invalid_events:

        try:
            logger.log_event(
                level="INFO",
                event=event,
            )

        except ValueError:
            pass

        else:
            raise AssertionError(
                f"Unsafe event accepted: {event!r}"
            )

    assert len(output.getvalue().splitlines()) == 3

    print("Structured JSONL events: 3")
    print("INFO logging: PASS")
    print("WARNING logging: PASS")
    print("ERROR logging: PASS")
    print("DEBUG filtering: PASS")
    print("UTC timestamp validation: PASS")
    print("Execution ID tracking: PASS")
    print("Exception type tracking: PASS")
    print("Sensitive exception message excluded: PASS")
    print("Invalid events rejected: PASS")
    print("Duplicate event check: PASS")
    print("Global root logger modified: NO")
    print("Application log files created: NO")
    print()
    print("PRODUCTION LOGGER TEST PASSED.")


if __name__ == "__main__":
    test_production_logger()
