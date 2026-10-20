
import hashlib
import json
import shutil
import tempfile

from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class RawLayerIngestor:

    def __init__(self):

        config_path = (
            PROJECT_ROOT
            / "config"
            / "platform_config.json"
        )

        with config_path.open(
            "r", encoding="utf-8"
        ) as file:
            self.config = json.load(file)

        source = self.config["source"]

        self.run_id = source["run_id"]

        self.source_dir = (
            PROJECT_ROOT / source["dataset_path"]
        ).resolve()

        self.product_master = (
            PROJECT_ROOT / source["product_master_path"]
        ).resolve()

        self.raw_root = PROJECT_ROOT / "data" / "raw"

        self.target = (
            self.raw_root / f"run_id={self.run_id}"
        )

    # ==============================================
    # FILE FINGERPRINT
    # ==============================================

    @staticmethod
    def file_hash(path):

        digest = hashlib.sha256()

        with path.open("rb") as file:

            for chunk in iter(
                lambda: file.read(1024 * 1024),
                b""
            ):
                digest.update(chunk)

        return digest.hexdigest()

    # ==============================================
    # DISCOVER ORIGINAL FILES
    # ==============================================

    def discover_sources(self):

        if not self.source_dir.is_dir():
            raise FileNotFoundError(self.source_dir)

        if not self.product_master.is_file():
            raise FileNotFoundError(self.product_master)

        # The six audited source datasets must exist
        # in both formats.
        for name in self.config["expected_datasets"]:

            for extension in ("csv", "jsonl"):

                path = (
                    self.source_dir
                    / f"{name}.{extension}"
                )

                if not path.is_file():
                    raise FileNotFoundError(path)

        manifest_path = (
            self.source_dir / "simulation_manifest.json"
        )

        if not manifest_path.is_file():
            raise FileNotFoundError(manifest_path)

        sources = {}

        # Preserve the full frozen run, including
        # its extra analytics outputs and metadata.
        for path in sorted(
            self.source_dir.rglob("*")
        ):

            if not path.is_file():
                continue

            relative = (
                Path("simulation")
                / path.relative_to(self.source_dir)
            )

            sources[relative.as_posix()] = path

        # Preserve the reference product master.
        sources["reference/product_master.json"] = (
            self.product_master
        )

        return sources

    # ==============================================
    # BUILD FILE MANIFEST
    # ==============================================

    def build_file_manifest(self, sources):

        result = {}

        for relative, path in sources.items():

            result[relative] = {
                "bytes": path.stat().st_size,
                "sha256": self.file_hash(path)
            }

        return result

    # ==============================================
    # VERIFY EXISTING SNAPSHOT
    # ==============================================

    def verify_snapshot(self, expected_files):

        manifest_path = (
            self.target / "_raw_manifest.json"
        )

        if not manifest_path.is_file():
            raise RuntimeError(
                "Existing raw snapshot has no manifest."
            )

        with manifest_path.open(
            "r", encoding="utf-8"
        ) as file:
            manifest = json.load(file)

        if manifest.get("run_id") != self.run_id:
            raise RuntimeError(
                "Raw snapshot run ID mismatch."
            )

        if manifest.get("files") != expected_files:
            raise RuntimeError(
                "Frozen source differs from "
                "existing raw snapshot."
            )

        actual_paths = {
            path.relative_to(self.target).as_posix()
            for path in self.target.rglob("*")
            if path.is_file()
        }

        expected_paths = (
            set(expected_files) | {"_raw_manifest.json"}
        )

        if actual_paths != expected_paths:
            raise RuntimeError(
                "Raw snapshot file inventory mismatch."
            )

        for relative, metadata in expected_files.items():

            path = self.target / relative

            if (
                path.stat().st_size != metadata["bytes"]
                or self.file_hash(path) != metadata["sha256"]
            ):
                raise RuntimeError(
                    f"Raw snapshot integrity failed: {relative}"
                )

        return manifest

    # ==============================================
    # INGEST RAW SNAPSHOT
    # ==============================================

    def ingest(self):

        sources = self.discover_sources()

        self.raw_root.mkdir(
            parents=True,
            exist_ok=True
        )

        expected_files = (
            self.build_file_manifest(sources)
        )

        # Rerunning must verify the original snapshot,
        # not silently overwrite it.
        if self.target.exists():

            manifest = self.verify_snapshot(
                expected_files
            )

            return {
                "status": "VERIFIED_EXISTING",
                "path": self.target,
                "manifest": manifest
            }

        manifest = {
            "run_id": self.run_id,
            "created_at_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            "file_count": len(expected_files),
            "files": expected_files
        }

        # Stage files first. Publish the snapshot only
        # after every copied file passes verification.
        with tempfile.TemporaryDirectory(
            prefix=".raw_stage_",
            dir=self.raw_root
        ) as temp_dir:

            stage = Path(temp_dir) / "snapshot"
            stage.mkdir()

            for relative, source_path in sources.items():

                destination = stage / relative

                destination.parent.mkdir(
                    parents=True,
                    exist_ok=True
                )

                shutil.copy2(
                    source_path,
                    destination
                )

                if (
                    self.file_hash(destination)
                    != expected_files[relative]["sha256"]
                ):
                    raise RuntimeError(
                        f"Copy integrity failed: {relative}"
                    )

            manifest_path = stage / "_raw_manifest.json"

            with manifest_path.open(
                "w", encoding="utf-8"
            ) as file:

                json.dump(
                    manifest,
                    file,
                    indent=2
                )

            stage.rename(self.target)

        return {
            "status": "CREATED",
            "path": self.target,
            "manifest": manifest
        }


if __name__ == "__main__":

    print("=" * 70)
    print("PHASE 8 - RAW LAYER INGESTION")
    print("=" * 70)

    ingestor = RawLayerIngestor()

    result = ingestor.ingest()

    print("\nSource run:")
    print(ingestor.run_id)

    print("\nSnapshot status:")
    print(result["status"])

    print("\nFiles verified:")
    print(result["manifest"]["file_count"])

    print("\nRaw layer location:")
    print(result["path"])

    print("\nManifest:")
    print(result["path"] / "_raw_manifest.json")

    print("\nRAW LAYER INGESTION PASSED.")
