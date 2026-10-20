
import json
import subprocess
import sys
import time

from .pipeline_logger import PipelineLogger, ROOT


def main():

    # ------------------------------------------
    # 1. Load configured simulation run
    # ------------------------------------------

    config_path = (
        ROOT / "config" / "platform_config.json"
    )

    with config_path.open(
        "r", encoding="utf-8"
    ) as file:
        config = json.load(file)

    source_run_id = config["source"]["run_id"]

    # ------------------------------------------
    # 2. Determine execution mode
    # ------------------------------------------

    args = sys.argv[1:]

    if args not in ([], ["--run"]):
        print(
            "Usage: python -m "
            "src.pipelines.run_with_logging [--run]"
        )
        return 2

    execute_pipeline = "--run" in args

    stage_name = (
        "pipeline_execution"
        if execute_pipeline
        else "pipeline_dry_run"
    )

    # ------------------------------------------
    # 3. Initialize logger
    # ------------------------------------------

    logger = PipelineLogger(
        source_run_id=source_run_id
    )

    command = [
        sys.executable,
        "-m",
        "src.pipelines.pipeline_runner",
        *args
    ]

    print("=" * 70, flush=True)
    print("PHASE 8 - LOGGED PIPELINE EXECUTION", flush=True)
    print("=" * 70, flush=True)

    print(
        f"Execution ID: {logger.execution_id}",
        flush=True
    )

    print(
        f"Source run: {source_run_id}",
        flush=True
    )

    print(
        f"Mode: {'RUN' if execute_pipeline else 'DRY RUN'}",
        flush=True
    )

    print(
        f"Log path: {logger.log_path}",
        flush=True
    )

    # ------------------------------------------
    # 4. Record execution start
    # ------------------------------------------

    logger.log(
        stage=stage_name,
        status="STARTED"
    )

    started = time.perf_counter()

    # ------------------------------------------
    # 5. Execute existing pipeline runner
    # ------------------------------------------

    try:

        result = subprocess.run(
            command,
            check=False
        )

        duration = (
            time.perf_counter() - started
        )

        if result.returncode != 0:

            logger.log(
                stage=stage_name,
                status="FAILED",
                duration_seconds=duration,
                error_type=(
                    f"PipelineExitCode{result.returncode}"
                )
            )

            print(
                "\nLOGGED PIPELINE EXECUTION FAILED."
            )

            return result.returncode

        logger.log(
            stage=stage_name,
            status="SUCCEEDED",
            duration_seconds=duration
        )

        print(
            "\nLOGGED PIPELINE EXECUTION PASSED."
        )

        return 0

    except KeyboardInterrupt:

        duration = (
            time.perf_counter() - started
        )

        logger.log(
            stage=stage_name,
            status="FAILED",
            duration_seconds=duration,
            error_type="KeyboardInterrupt"
        )

        print("\nPipeline execution interrupted.")

        return 130

    except Exception as exc:

        duration = (
            time.perf_counter() - started
        )

        logger.log(
            stage=stage_name,
            status="FAILED",
            duration_seconds=duration,
            error_type=type(exc).__name__
        )

        print(
            f"\nPipeline execution error: "
            f"{type(exc).__name__}"
        )

        return 1


if __name__ == "__main__":
    sys.exit(main())
