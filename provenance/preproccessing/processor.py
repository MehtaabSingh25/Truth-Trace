
from pathlib import Path
from datetime import datetime
import json
import uuid
import sys

MEDIA_DNA_DIR = Path(__file__).resolve().parent.parent / "media_dna"
sys.path.insert(0, str(MEDIA_DNA_DIR))

from media_features import analyze_media


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

COLLECTOR_OUTPUT_DIR = (
    BASE_DIR.parent /
    "collector" /
    "outputs"
)

OUTPUT_DIR = BASE_DIR / "outputs"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# PREPROCESSOR
# ============================================================

class ArtifactPreprocessor:

    def __init__(self, investigation_dir):

        self.investigation_dir = Path(
            investigation_dir
        )

        self.investigation_id = (
            self.investigation_dir.name
        )

        self.output_dir = (
            OUTPUT_DIR /
            self.investigation_id
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

    # ========================================================
    # FIND ARTIFACTS
    # ========================================================

    def find_artifacts(self):

        artifacts = []

        for media_file in self.investigation_dir.rglob("*"):

            if not media_file.is_file():
                continue

            # Only process files inside media directories
            if media_file.parent.name != "media":
                continue

            artifacts.append(media_file)

        return artifacts

    # ========================================================
    # PROCESS SINGLE ARTIFACT
    # ========================================================

    def process_artifact(self, file_path):

        artifact_id = (
            f"artifact_"
            f"{uuid.uuid4().hex[:12]}"
        )

        print(
            f"  Processing: "
            f"{file_path.name}"
        )

        analysis = analyze_media(
            file_path
        )

        record = {
            "artifact_id": artifact_id,

            "investigation_id":
                self.investigation_id,

            "source_file":
                str(file_path),

            "collected_at":
                datetime.now().isoformat(),

            "analysis": analysis
        }

        return record

    # ========================================================
    # PROCESS INVESTIGATION
    # ========================================================

    def process(self):

        print()
        print("=" * 60)
        print("              TRUTH TRACE PREPROCESSING")
        print("=" * 60)

        print(
            f"\nInvestigation: "
            f"{self.investigation_id}"
        )

        artifacts = self.find_artifacts()

        print(
            f"Artifacts discovered: "
            f"{len(artifacts)}"
        )

        records = []

        for artifact in artifacts:

            try:

                record = self.process_artifact(
                    artifact
                )

                records.append(record)

            except Exception as error:

                print(
                    f"  ERROR: "
                    f"{artifact.name}: "
                    f"{error}"
                )

        # ----------------------------------------------------
        # SAVE ARTIFACT INDEX
        # ----------------------------------------------------

        output_file = (
            self.output_dir /
            "artifacts.json"
        )

        output = {
            "investigation_id":
                self.investigation_id,

            "processor": {
                "name":
                    "Truth Trace Artifact Preprocessor",

                "version":
                    "1.0"
            },

            "processed_at":
                datetime.now().isoformat(),

            "artifact_count":
                len(records),

            "artifacts":
                records
        }

        with open(
            output_file,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                output,
                file,
                indent=4
            )

        # ----------------------------------------------------
        # COMPLETE
        # ----------------------------------------------------

        print()
        print("=" * 60)
        print("              PREPROCESSING COMPLETE")
        print("=" * 60)

        print(
            f"\nArtifacts processed: "
            f"{len(records)}"
        )

        print(
            f"Output: "
            f"{output_file}"
        )

        return output_file


# ============================================================
# FIND LATEST INVESTIGATION
# ============================================================

def get_latest_investigation():

    investigations = [
        path
        for path in COLLECTOR_OUTPUT_DIR.iterdir()
        if path.is_dir()
    ]

    if not investigations:

        raise FileNotFoundError(
            "No collector investigations found."
        )

    return max(
        investigations,
        key=lambda path: path.stat().st_mtime
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    investigation = get_latest_investigation()

    preprocessor = ArtifactPreprocessor(
        investigation
    )

    preprocessor.process()
