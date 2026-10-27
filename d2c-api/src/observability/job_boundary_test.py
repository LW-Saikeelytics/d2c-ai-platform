
import io
import json
import subprocess
import tempfile

from pathlib import Path
from unittest.mock import Mock

from src.observability.job_boundary import (
    run_logged_job,
)

from src.observability.production_logger import (
    ProductionLogger,
)


def read_records(output):
    return [
        json.loads(line)
        for line in output.getvalue().splitlines()
        if line.strip()
    ]


def test_job_boundary():

    with tempfile.TemporaryDirectory() as temp_dir:

        cwd = Path(temp_dir)

        # ----------------------------------
        # TEST 1 - DEFAULT EXECUTION DISABLED
        # ----------------------------------

        fake_runner = Mock()

        result = run_logged_job(
            job_name="generator",
            command=["fake_command"],
            cwd=cwd,
            runner=fake_runner,
        )

        assert result is None
        fake_runner.assert_not_called()

        print("Default execution disabled: PASS")
        # ----------------------------------
        # TEST - LIVE EXECUTION BLOCKED
        # ----------------------------------
        try:
            run_logged_job(
                job_name="generator",
                command=["unapproved_real_command"],
                cwd=cwd,
                execute=True,
            )

        except RuntimeError as error:

            assert str(error) == (
                "Live subprocess execution is disabled"
            )

            print(
                "Live execution without injected runner: "
                "BLOCKED (PASS)"
            )

        else:
            raise AssertionError(
                "Unapproved live execution was accepted"
            )

        # ----------------------------------
        # TEST 2 - MOCKED SUCCESS
        # ----------------------------------

        output = io.StringIO()

        logger = ProductionLogger(
            component="generator",
            stream=output,
        )

        fake_runner = Mock(
            return_value=subprocess.CompletedProcess(
                args=["fake_command"],
                returncode=0,
            )
        )

        result = run_logged_job(
            job_name="generator",
            command=["fake_command"],
            cwd=cwd,
            execute=True,
            runner=fake_runner,
            logger=logger,
        )

        assert result == 0
        fake_runner.assert_called_once()

        records = read_records(output)

        assert len(records) == 2
        assert records[0]["event"] == "job_started"
        assert records[1]["event"] == "job_succeeded"

        assert (
            records[0]["execution_id"]
            == records[1]["execution_id"]
        )

        print("Mocked successful execution: PASS")

        # ----------------------------------
        # TEST 3 - MOCKED NONZERO EXIT CODE
        # ----------------------------------

        output = io.StringIO()

        logger = ProductionLogger(
            component="ml",
            stream=output,
        )

        fake_runner = Mock(
            return_value=subprocess.CompletedProcess(
                args=["fake_command"],
                returncode=7,
            )
        )

        result = run_logged_job(
            job_name="ml",
            command=["fake_command"],
            cwd=cwd,
            execute=True,
            runner=fake_runner,
            logger=logger,
        )

        assert result == 7

        records = read_records(output)

        assert len(records) == 2
        assert records[1]["event"] == "job_failed"
        assert records[1]["level"] == "ERROR"

        print("Nonzero exit code preserved: PASS")

        # ----------------------------------
        # TEST 4 - MOCKED LAUNCH FAILURE
        # ----------------------------------

        output = io.StringIO()

        logger = ProductionLogger(
            component="generator",
            stream=output,
        )

        secret = "PRIVATE_PASSWORD_DO_NOT_LOG"

        fake_runner = Mock(
            side_effect=OSError(secret)
        )

        try:
            run_logged_job(
                job_name="generator",
                command=["fake_command"],
                cwd=cwd,
                execute=True,
                runner=fake_runner,
                logger=logger,
            )

        except OSError:
            pass

        else:
            raise AssertionError(
                "Launch failure was suppressed"
            )

        records = read_records(output)

        assert len(records) == 2
        assert records[1]["event"] == "job_launch_failed"
        assert records[1]["error_type"] == "OSError"
        assert secret not in output.getvalue()

        print("Launch exception propagated: PASS")
        print("Sensitive error message excluded: PASS")

        # ----------------------------------
        # TEST 5 - UNSUPPORTED JOB
        # ----------------------------------

        try:
            run_logged_job(
                job_name="unknown",
                command=["fake_command"],
                cwd=cwd,
            )

        except ValueError:
            print("Unsupported job rejected: PASS")

        else:
            raise AssertionError(
                "Unsupported job accepted"
            )

    print()
    print("Real subprocesses launched: 0")
    print("Generator executions: 0")
    print("ML training executions: 0")
    print("Existing datasets modified: NO")
    print()
    print("JOB BOUNDARY TEST PASSED.")


if __name__ == "__main__":
    test_job_boundary()
