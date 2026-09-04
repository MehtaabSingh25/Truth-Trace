
from pathlib import Path
from datetime import datetime
import json


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

MEDIA_DNA_OUTPUT_DIR = (
    BASE_DIR.parent /
    "media_dna" /
    "outputs"
)

OUTPUT_DIR = BASE_DIR / "outputs"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# HASH DISTANCE
# ============================================================

def hamming_distance(hash_a, hash_b):

    if not hash_a or not hash_b:
        return None

    if len(hash_a) != len(hash_b):
        return None

    value_a = int(hash_a, 16)
    value_b = int(hash_b, 16)

    xor_value = value_a ^ value_b

    return bin(xor_value).count("1")


# ============================================================
# HASH SIMILARITY
# ============================================================

def hash_similarity(hash_a, hash_b):

    distance = hamming_distance(
        hash_a,
        hash_b
    )

    if distance is None:
        return 0.0

    # imagehash hashes are normally 64 bits.
    max_distance = len(hash_a) * 4

    similarity = (
        1 -
        (distance / max_distance)
    )

    return round(
        max(0.0, similarity),
        6
    )


# ============================================================
# ASPECT RATIO SIMILARITY
# ============================================================

def aspect_ratio_similarity(
    ratio_a,
    ratio_b
):

    if ratio_a is None or ratio_b is None:
        return 0.0

    difference = abs(
        ratio_a - ratio_b
    )

    # A difference of 0 means perfect similarity.
    # Larger differences reduce the score.

    similarity = max(
        0.0,
        1 - difference
    )

    return round(
        similarity,
        6
    )


# ============================================================
# DIMENSION SIMILARITY
# ============================================================

def dimension_similarity(
    width_a,
    height_a,
    width_b,
    height_b
):

    if not all([
        width_a,
        height_a,
        width_b,
        height_b
    ]):
        return 0.0

    width_ratio = (
        min(width_a, width_b) /
        max(width_a, width_b)
    )

    height_ratio = (
        min(height_a, height_b) /
        max(height_a, height_b)
    )

    similarity = (
        width_ratio +
        height_ratio
    ) / 2

    return round(
        similarity,
        6
    )


# ============================================================
# HISTOGRAM SIMILARITY
# ============================================================

def histogram_similarity(
    histogram_a,
    histogram_b
):

    if not histogram_a or not histogram_b:
        return 0.0

    if len(histogram_a) != len(histogram_b):
        return 0.0

    # Histogram intersection.
    intersection = sum(
        min(a, b)
        for a, b in zip(
            histogram_a,
            histogram_b
        )
    )

    return round(
        intersection,
        6
    )


# ============================================================
# ARTIFACT COMPARISON
# ============================================================

def compare_artifacts(
    artifact_a,
    artifact_b
):

    dna_a = artifact_a["dna"]
    dna_b = artifact_b["dna"]

    # --------------------------------------------------------
    # EXACT HASH
    # --------------------------------------------------------

    exact_match = (
        dna_a["sha256"] ==
        dna_b["sha256"]
    )

    # --------------------------------------------------------
    # PERCEPTUAL HASHES
    # --------------------------------------------------------

    phash_similarity = hash_similarity(
        dna_a["perceptual_hash"]["phash"],
        dna_b["perceptual_hash"]["phash"]
    )

    dhash_similarity = hash_similarity(
        dna_a["perceptual_hash"]["dhash"],
        dna_b["perceptual_hash"]["dhash"]
    )

    ahash_similarity = hash_similarity(
        dna_a["perceptual_hash"]["ahash"],
        dna_b["perceptual_hash"]["ahash"]
    )

    # --------------------------------------------------------
    # DIMENSIONS
    # --------------------------------------------------------

    dimensions = dimension_similarity(
        dna_a.get("width"),
        dna_a.get("height"),
        dna_b.get("width"),
        dna_b.get("height")
    )

    # --------------------------------------------------------
    # ASPECT RATIO
    # --------------------------------------------------------

    aspect_ratio = aspect_ratio_similarity(
        dna_a.get("aspect_ratio"),
        dna_b.get("aspect_ratio")
    )

    # --------------------------------------------------------
    # HISTOGRAM
    # --------------------------------------------------------

    histogram = histogram_similarity(
        dna_a.get("color_histogram"),
        dna_b.get("color_histogram")
    )

    # --------------------------------------------------------
    # OVERALL SCORE
    # --------------------------------------------------------

    #
    # We intentionally give perceptual hashes the
    # highest weight because they are the strongest
    # evidence of visual similarity.
    #

    overall_score = (
        (phash_similarity * 0.35) +
        (dhash_similarity * 0.20) +
        (ahash_similarity * 0.15) +
        (histogram * 0.20) +
        (aspect_ratio * 0.05) +
        (dimensions * 0.05)
    )

    overall_score = round(
        overall_score,
        6
    )

    # --------------------------------------------------------
    # CONFIDENCE
    # --------------------------------------------------------

    if exact_match:

        confidence = "EXACT"

    elif overall_score >= 0.90:

        confidence = "HIGH"

    elif overall_score >= 0.75:

        confidence = "MEDIUM"

    elif overall_score >= 0.60:

        confidence = "LOW"

    else:

        confidence = "MINIMAL"

    return {

        "artifact_a":
            artifact_a["artifact_id"],

        "artifact_b":
            artifact_b["artifact_id"],

        "exact_sha256_match":
            exact_match,

        "signals": {

            "phash_similarity":
                phash_similarity,

            "dhash_similarity":
                dhash_similarity,

            "ahash_similarity":
                ahash_similarity,

            "histogram_similarity":
                histogram,

            "aspect_ratio_similarity":
                aspect_ratio,

            "dimension_similarity":
                dimensions
        },

        "overall_similarity":
            overall_score,

        "confidence":
            confidence
    }


# ============================================================
# FIND LATEST DNA
# ============================================================

def get_latest_investigation():

    investigations = [
        path
        for path in MEDIA_DNA_OUTPUT_DIR.iterdir()
        if path.is_dir()
    ]

    if not investigations:

        raise FileNotFoundError(
            "No Media DNA output found."
        )

    return max(
        investigations,
        key=lambda path: path.stat().st_mtime
    )


# ============================================================
# LOAD DNA
# ============================================================

def load_media_dna(
    investigation_id
):

    dna_file = (
        MEDIA_DNA_OUTPUT_DIR /
        investigation_id /
        "media_dna.json"
    )

    if not dna_file.exists():

        raise FileNotFoundError(
            f"Media DNA file not found: "
            f"{dna_file}"
        )

    with open(
        dna_file,
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
    print("              TRUTH TRACE SIMILARITY")
    print("=" * 60)

    # --------------------------------------------------------
    # FIND INVESTIGATION
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
    # LOAD DNA
    # --------------------------------------------------------

    dna_data = load_media_dna(
        investigation_id
    )

    artifacts = dna_data.get(
        "artifacts",
        []
    )

    print(
        f"Artifacts found: "
        f"{len(artifacts)}"
    )

    # --------------------------------------------------------
    # COMPARE EVERY PAIR
    # --------------------------------------------------------

    comparisons = []

    total_pairs = (
        len(artifacts) *
        (len(artifacts) - 1)
    ) // 2

    print(
        f"Comparisons required: "
        f"{total_pairs}"
    )

    for i in range(
        len(artifacts)
    ):

        for j in range(
            i + 1,
            len(artifacts)
        ):

            artifact_a = artifacts[i]
            artifact_b = artifacts[j]

            result = compare_artifacts(
                artifact_a,
                artifact_b
            )

            comparisons.append(
                result
            )

    # --------------------------------------------------------
    # SORT BY SIMILARITY
    # --------------------------------------------------------

    comparisons.sort(
        key=lambda item:
            item["overall_similarity"],
        reverse=True
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
    # SAVE
    # --------------------------------------------------------

    output = {

        "investigation_id":
            investigation_id,

        "engine": {

            "name":
                "Truth Trace Similarity Engine",

            "version":
                "1.0"
        },

        "generated_at":
            datetime.now().isoformat(),

        "artifact_count":
            len(artifacts),

        "comparison_count":
            len(comparisons),

        "comparisons":
            comparisons
    }

    output_file = (
        investigation_output /
        "similarity.json"
    )

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
    # SHOW TOP MATCHES
    # --------------------------------------------------------

    print()
    print("TOP SIMILARITY MATCHES")
    print("-" * 60)

    for comparison in comparisons[:10]:

        print(
            f"{comparison['artifact_a']}"
            f" <-> "
            f"{comparison['artifact_b']}"
        )

        print(
            f"  Score: "
            f"{comparison['overall_similarity']}"
        )

        print(
            f"  Confidence: "
            f"{comparison['confidence']}"
        )

        print()

    # --------------------------------------------------------
    # COMPLETE
    # --------------------------------------------------------

    print("=" * 60)
    print("              SIMILARITY COMPLETE")
    print("=" * 60)

    print(
        f"\nTotal comparisons: "
        f"{len(comparisons)}"
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

