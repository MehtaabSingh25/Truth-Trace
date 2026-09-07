
from pathlib import Path
from datetime import datetime
import hashlib
import json

from PIL import Image
import imagehash


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

PREPROCESSING_OUTPUT_DIR = (
    BASE_DIR.parent /
    "preproccessing" /
    "outputs"
)

OUTPUT_DIR = BASE_DIR / "outputs"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# HASH
# ============================================================

def calculate_sha256(file_path):

    sha256 = hashlib.sha256()

    with open(
        file_path,
        "rb"
    ) as file:

        while chunk := file.read(8192):

            sha256.update(chunk)

    return sha256.hexdigest()


# ============================================================
# COLOR HISTOGRAM
# ============================================================

def calculate_color_histogram(image):

    rgb_image = image.convert("RGB")

    histogram = rgb_image.histogram()

    # Normalize histogram so image size does not
    # directly affect the values.

    total = sum(histogram)

    if total == 0:
        return []

    normalized = [
        round(value / total, 8)
        for value in histogram
    ]

    return normalized


# ============================================================
# MEDIA DNA
# ============================================================

def extract_media_dna(file_path):
    file_path = Path(file_path)
    from media_features import analyze_media
    return analyze_media(file_path)


# ============================================================
# FIND INVESTIGATION
# ============================================================

def get_latest_investigation():

    if not PREPROCESSING_OUTPUT_DIR.is_dir():
        raise FileNotFoundError(
            f"Preprocessing output directory not found: "
            f"{PREPROCESSING_OUTPUT_DIR}"
        )

    investigations = [
        path
        for path in PREPROCESSING_OUTPUT_DIR.iterdir()
        if path.is_dir()
    ]

    if not investigations:

        raise FileNotFoundError(
            "No preprocessing output found."
        )

    return max(
        investigations,
        key=lambda path: path.stat().st_mtime
    )


# ============================================================
# LOAD ARTIFACT INDEX
# ============================================================

def load_artifacts(
    investigation_id
):

    artifact_file = (
        PREPROCESSING_OUTPUT_DIR /
        investigation_id /
        "artifacts.json"
    )

    if not artifact_file.exists():

        raise FileNotFoundError(
            f"Artifact index not found: "
            f"{artifact_file}"
        )

    with open(
        artifact_file,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# ============================================================
# MAIN
# ============================================================

def run():

    print()
    print("=" * 60)
    print("              TRUTH TRACE MEDIA DNA")
    print("=" * 60)

    # --------------------------------------------------------
    # FIND LATEST INVESTIGATION
    # --------------------------------------------------------

    investigation_dir = (
        get_latest_investigation()
    )

    investigation_id = (
        investigation_dir.name
    )

    print(
        f"\nInvestigation: "
        f"{investigation_id}"
    )

    # --------------------------------------------------------
    # LOAD ARTIFACTS
    # --------------------------------------------------------

    artifact_data = load_artifacts(
        investigation_id
    )

    artifacts = artifact_data.get(
        "artifacts",
        []
    )

    print(
        f"Artifacts found: "
        f"{len(artifacts)}"
    )

    # --------------------------------------------------------
    # OUTPUT DIRECTORY
    # --------------------------------------------------------

    investigation_output = (
        OUTPUT_DIR /
        investigation_id
    )

    investigation_output.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # EXTRACT DNA
    # --------------------------------------------------------

    dna_records = []

    for artifact in artifacts:

        artifact_id = artifact[
            "artifact_id"
        ]

        source_file = Path(
            artifact["source_file"]
        )

        print(
            f"  Extracting DNA: "
            f"{source_file.name}"
        )

        try:

            dna = extract_media_dna(
                source_file
            )

            record = {
                "artifact_id":
                    artifact_id,

                "source_file":
                    str(source_file),

                "dna":
                    dna
            }

            dna_records.append(
                record
            )

        except Exception as error:

            print(
                f"  ERROR: "
                f"{source_file.name}: "
                f"{error}"
            )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    output_file = (
        investigation_output /
        "media_dna.json"
    )

    output = {

        "investigation_id":
            investigation_id,

        "extractor": {

            "name":
                "Truth Trace Media DNA",

            "version":
                "1.0"
        },

        "extracted_at":
            datetime.now().isoformat(),

        "artifact_count":
            len(dna_records),

        "artifacts":
            dna_records
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

    # --------------------------------------------------------
    # COMPLETE
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("              MEDIA DNA COMPLETE")
    print("=" * 60)

    print(
        f"\nArtifacts fingerprinted: "
        f"{len(dna_records)}"
    )

    print(
        f"Output: "
        f"{output_file}"
    )

    print()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    run()
