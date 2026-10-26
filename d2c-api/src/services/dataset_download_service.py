
import re

from pathlib import Path, PurePosixPath

from src.runtime.run_workspace import RUNTIME_ROOT

from src.services.dataset_catalog_service import (
    DATASET_GROUPS,
    locate_dataset_root,
)


# =====================================================
# PHASE 9.7.4A - SAFE DATASET DOWNLOAD RESOLVER
# =====================================================

MEDIA_TYPES = {
    ".csv": "text/csv",
    ".jsonl": "application/x-ndjson",
    ".json": "application/json",
}

DATASET_FILES = {
    name.replace("/", "__"): name
    for filenames in DATASET_GROUPS.values()
    for name in filenames
}

DATASET_ID_PATTERN = re.compile(
    r"^[a-z0-9_]+\.(?:csv|jsonl|json)$"
)


class DatasetNotFoundError(LookupError):
    """Dataset identifier is not registered."""


class DatasetFileUnavailableError(RuntimeError):
    """An approved dataset file is missing or unsafe."""


def resolve_dataset_download(
    run_id,
    dataset_id,
    runs_root=RUNTIME_ROOT,
):

    # Validate the dataset identifier.
    if (
        not isinstance(dataset_id, str)
        or not DATASET_ID_PATTERN.fullmatch(dataset_id)
    ):
        raise ValueError("Invalid dataset identifier")

    # Only approved Phase 6 output files are allowed.
    relative_name = DATASET_FILES.get(dataset_id)

    if relative_name is None:
        raise DatasetNotFoundError(
            "Dataset is not registered"
        )

    # Reuse completed-run validation.
    dataset_root = locate_dataset_root(
        run_id,
        runs_root,
    )

    # Convert a trusted POSIX relative filename
    # into a path within the dataset directory.
    parts = PurePosixPath(relative_name).parts

    file_path = dataset_root.joinpath(*parts)

    # Block symlinks in the selected file and
    # any subdirectories below the dataset root.
    current = dataset_root

    for part in parts:
        current = current / part

        if current.is_symlink():
            raise DatasetFileUnavailableError(
                "Unsafe dataset link"
            )

    if not file_path.is_file():
        raise DatasetFileUnavailableError(
            "Dataset file is unavailable"
        )

    try:
        root_resolved = dataset_root.resolve(strict=True)
        file_resolved = file_path.resolve(strict=True)

        # Reject any path that escapes the dataset root.
        file_resolved.relative_to(root_resolved)

        file_size = file_path.stat().st_size

    except (OSError, ValueError) as exc:
        raise DatasetFileUnavailableError(
            "Dataset path verification failed"
        ) from exc

    media_type = MEDIA_TYPES.get(file_path.suffix)

    if media_type is None:
        raise DatasetFileUnavailableError(
            "Unsupported dataset format"
        )

    # This return value is INTERNAL ONLY.
    # Future HTTP responses must not serialize
    # file_path to the user.
    return {
        "dataset_id": dataset_id,
        "file_path": file_resolved,
        "filename": file_path.name,
        "media_type": media_type,
        "size_bytes": file_size,
    }
