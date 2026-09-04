from pathlib import Path
from datetime import datetime
import json


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent

COLLECTOR_OUTPUT_DIR = (
    PROJECT_ROOT /
    "provenance" /
    "collector" /
    "outputs"
)

MEDIA_DNA_OUTPUT_DIR = (
    PROJECT_ROOT /
    "provenance" /
    "media_dna" /
    "outputs"
)

SIMILARITY_OUTPUT_DIR = (
    PROJECT_ROOT /
    "provenance" /
    "similarity" /
    "outputs"
)

LINEAGE_OUTPUT_DIR = (
    PROJECT_ROOT /
    "provenance" /
    "lineage" /
    "outputs"
)

OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def load_json(path):

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def get_latest_investigation():

    investigations = [
        path
        for path in MEDIA_DNA_OUTPUT_DIR.iterdir()
        if path.is_dir()
    ]

    if not investigations:
        raise FileNotFoundError(
            "No investigation found."
        )

    return max(
        investigations,
        key=lambda path: path.stat().st_mtime
    )


# ---------------------------------------------------------
# LOAD PIPELINE OUTPUTS
# ---------------------------------------------------------

def load_pipeline_data(investigation_id):

    dna_file = (
        MEDIA_DNA_OUTPUT_DIR /
        investigation_id /
        "media_dna.json"
    )

    similarity_file = (
        SIMILARITY_OUTPUT_DIR /
        investigation_id /
        "similarity.json"
    )

    lineage_file = (
        LINEAGE_OUTPUT_DIR /
        investigation_id /
        "lineage.json"
    )

    if not dna_file.exists():
        raise FileNotFoundError(
            f"Missing Media DNA: {dna_file}"
        )

    if not similarity_file.exists():
        raise FileNotFoundError(
            f"Missing Similarity: {similarity_file}"
        )

    if not lineage_file.exists():
        raise FileNotFoundError(
            f"Missing Lineage: {lineage_file}"
        )

    return {
        "dna": load_json(dna_file),
        "similarity": load_json(similarity_file),
        "lineage": load_json(lineage_file)
    }


# ---------------------------------------------------------
# PLATFORM SUMMARY
# ---------------------------------------------------------

def build_platform_summary(lineage):

    platforms = {}

    for node in lineage["graph"]["nodes"]:

        platform = node.get("platform")

        if not platform:
            continue

        if platform not in platforms:
            platforms[platform] = {
                "artifacts": 0,
                "artifact_ids": []
            }

        platforms[platform]["artifacts"] += 1

        platforms[platform]["artifact_ids"].append(
            node["artifact_id"]
        )

    return platforms


# ---------------------------------------------------------
# ROOT SUMMARY
# ---------------------------------------------------------

def build_root_summary(lineage):

    roots = []

    nodes = {
        node["artifact_id"]: node
        for node in lineage["graph"]["nodes"]
    }

    for artifact_id in lineage["graph"]["roots"]:

        node = nodes.get(artifact_id)

        if not node:
            continue

        roots.append({
            "artifact_id": artifact_id,
            "platform": node.get("platform"),
            "post_id": node.get("post_id"),
            "username": node.get("username"),
            "created_at": node.get("created_at"),
            "file": node.get("file")
        })

    return roots


# ---------------------------------------------------------
# EDGE SUMMARY
# ---------------------------------------------------------

def build_edge_summary(lineage):

    edges = []

    for edge in lineage["graph"]["edges"]:

        edges.append({
            "parent": edge["parent"],
            "child": edge["child"],
            "similarity": edge["similarity_score"],
            "confidence": edge["confidence"],
            "confidence_score": edge["confidence_score"],
            "reasons": edge["reasons"]
        })

    edges.sort(
        key=lambda item: item["confidence_score"],
        reverse=True
    )

    return edges


# ---------------------------------------------------------
# PLATFORM TRANSITIONS
# ---------------------------------------------------------

def build_platform_transitions(
    lineage
):

    nodes = {
        node["artifact_id"]: node
        for node in lineage["graph"]["nodes"]
    }

    transitions = {}

    for edge in lineage["graph"]["edges"]:

        parent = nodes.get(
            edge["parent"]
        )

        child = nodes.get(
            edge["child"]
        )

        if not parent or not child:
            continue

        parent_platform = parent.get(
            "platform"
        )

        child_platform = child.get(
            "platform"
        )

        if not parent_platform or not child_platform:
            continue

        if parent_platform == child_platform:
            continue

        key = (
            f"{parent_platform}"
            f" -> "
            f"{child_platform}"
        )

        if key not in transitions:
            transitions[key] = 0

        transitions[key] += 1

    return transitions


# ---------------------------------------------------------
# CONFIDENCE SUMMARY
# ---------------------------------------------------------

def build_confidence_summary(lineage):

    summary = {
        "VERY_HIGH": 0,
        "HIGH": 0,
        "MEDIUM": 0,
        "LOW": 0
    }

    for edge in lineage["graph"]["edges"]:

        confidence = edge.get(
            "confidence"
        )

        if confidence in summary:
            summary[confidence] += 1

    return summary


# ---------------------------------------------------------
# TEXT REPORT
# ---------------------------------------------------------

def generate_text_report(
    investigation_id,
    dna,
    similarity,
    lineage
):

    graph = lineage["graph"]

    platforms = build_platform_summary(
        lineage
    )

    roots = build_root_summary(
        lineage
    )

    edges = build_edge_summary(
        lineage
    )

    transitions = build_platform_transitions(
        lineage
    )

    confidence = build_confidence_summary(
        lineage
    )

    lines = []

    lines.append(
        "=" * 70
    )

    lines.append(
        "                 TRUTH TRACE"
    )

    lines.append(
        "             MEDIA PROVENANCE REPORT"
    )

    lines.append(
        "=" * 70
    )

    lines.append("")

    lines.append(
        f"Investigation ID: {investigation_id}"
    )

    lines.append(
        f"Generated: {datetime.now().isoformat()}"
    )

    lines.append("")

    lines.append(
        "------------------------------------------------------------"
    )

    lines.append(
        "EVIDENCE SUMMARY"
    )

    lines.append(
        "------------------------------------------------------------"
    )

    lines.append(
        f"Artifacts analyzed: "
        f"{len(dna.get('artifacts', []))}"
    )

    lines.append(
        f"Similarity comparisons: "
        f"{len(similarity.get('comparisons', []))}"
    )

    lines.append(
        f"Inferred lineage nodes: "
        f"{len(graph['nodes'])}"
    )

    lines.append(
        f"Inferred lineage edges: "
        f"{len(graph['edges'])}"
    )

    lines.append("")

    lines.append(
        "------------------------------------------------------------"
    )

    lines.append(
        "PLATFORM DISTRIBUTION"
    )

    lines.append(
        "------------------------------------------------------------"
    )

    for platform, data in platforms.items():

        lines.append(
            f"{platform}: "
            f"{data['artifacts']} artifacts"
        )

    lines.append("")

    lines.append(
        "------------------------------------------------------------"
    )

    lines.append(
        "LIKELY ROOT ARTIFACTS"
    )

    lines.append(
        "------------------------------------------------------------"
    )

    if roots:

        for root in roots:

            lines.append(
                f"{root['artifact_id']}"
            )

            lines.append(
                f"  Platform: "
                f"{root['platform']}"
            )

            lines.append(
                f"  Post ID: "
                f"{root['post_id']}"
            )

            lines.append(
                f"  User: "
                f"{root['username']}"
            )

            lines.append(
                f"  Created: "
                f"{root['created_at']}"
            )

            lines.append("")

    else:

        lines.append(
            "No root artifacts identified."
        )

    lines.append(
        "------------------------------------------------------------"
    )

    lines.append(
        "PLATFORM TRANSITIONS"
    )

    lines.append(
        "------------------------------------------------------------"
    )

    if transitions:

        for transition, count in transitions.items():

            lines.append(
                f"{transition}: "
                f"{count} inferred edge(s)"
            )

    else:

        lines.append(
            "No cross-platform transitions identified."
        )

    lines.append("")

    lines.append(
        "------------------------------------------------------------"
    )

    lines.append(
        "LINEAGE CONFIDENCE"
    )

    lines.append(
        "------------------------------------------------------------"
    )

    for level, count in confidence.items():

        lines.append(
            f"{level}: {count}"
        )

    lines.append("")

    lines.append(
        "------------------------------------------------------------"
    )

    lines.append(
        "INFERRED LINEAGE EDGES"
    )

    lines.append(
        "------------------------------------------------------------"
    )

    if edges:

        for edge in edges:

            lines.append(
                f"{edge['parent']} "
                f"--> "
                f"{edge['child']}"
            )

            lines.append(
                f"  Similarity: "
                f"{edge['similarity']}"
            )

            lines.append(
                f"  Confidence: "
                f"{edge['confidence']} "
                f"({edge['confidence_score']})"
            )

            lines.append(
                f"  Evidence: "
                f"{', '.join(edge['reasons'])}"
            )

            lines.append("")

    else:

        lines.append(
            "No lineage edges inferred."
        )

    lines.append(
        "------------------------------------------------------------"
    )

    lines.append(
        "INVESTIGATOR INTERPRETATION"
    )

    lines.append(
        "------------------------------------------------------------"
    )

    lines.append(
        "The lineage graph above represents "
        "relationships independently inferred "
        "from collected media evidence."
    )

    lines.append(
        "It is not generated from the propagation "
        "simulator's ground-truth manifest."
    )

    lines.append("")

    lines.append(
        "IMPORTANT: A lineage edge represents "
        "evidence of a likely relationship, "
        "not absolute proof of causation."
    )

    lines.append("")

    lines.append(
        "=" * 70
    )

    lines.append(
        "                 END OF REPORT"
    )

    lines.append(
        "=" * 70
    )

    return "\n".join(lines)


# ---------------------------------------------------------
# JSON REPORT
# ---------------------------------------------------------

def generate_json_report(
    investigation_id,
    dna,
    similarity,
    lineage
):

    graph = lineage["graph"]

    return {

        "report": {
            "name":
                "Truth Trace Media Provenance Report",

            "version":
                "1.0",

            "investigation_id":
                investigation_id,

            "generated_at":
                datetime.now().isoformat()
        },

        "evidence": {

            "artifact_count":
                len(dna.get("artifacts", [])),

            "comparison_count":
                len(
                    similarity.get(
                        "comparisons",
                        []
                    )
                )
        },

        "lineage": {

            "node_count":
                len(graph["nodes"]),

            "edge_count":
                len(graph["edges"]),

            "roots":
                graph["roots"],

            "leaves":
                graph["leaves"],

            "edges":
                graph["edges"]
        },

        "platform_distribution":
            build_platform_summary(
                lineage
            ),

        "platform_transitions":
            build_platform_transitions(
                lineage
            ),

        "confidence_summary":
            build_confidence_summary(
                lineage
            ),

        "likely_roots":
            build_root_summary(
                lineage
            ),

        "methodology": {

            "ground_truth_used":
                False,

            "description":
                "Lineage was independently inferred "
                "from collected artifact metadata "
                "and media similarity evidence."
        }
    }


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def run():

    print()

    print(
        "=" * 60
    )

    print(
        "              TRUTH TRACE REPORTING"
    )

    print(
        "=" * 60
    )

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

    data = load_pipeline_data(
        investigation_id
    )

    dna = data["dna"]
    similarity = data["similarity"]
    lineage = data["lineage"]

    print(
        f"Artifacts: "
        f"{len(dna.get('artifacts', []))}"
    )

    print(
        f"Comparisons: "
        f"{len(similarity.get('comparisons', []))}"
    )

    print(
        f"Lineage edges: "
        f"{len(lineage['graph']['edges'])}"
    )

    output_dir = (
        OUTPUT_DIR /
        investigation_id
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    # Text report

    text_report = generate_text_report(
        investigation_id,
        dna,
        similarity,
        lineage
    )

    text_file = (
        output_dir /
        "report.txt"
    )

    with open(
        text_file,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            text_report
        )

    # JSON report

    json_report = generate_json_report(
        investigation_id,
        dna,
        similarity,
        lineage
    )

    json_file = (
        output_dir /
        "report.json"
    )

    with open(
        json_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            json_report,
            file,
            indent=4
        )

    print()

    print(
        "REPORTING COMPLETE"
    )

    print(
        f"\nText report:"
        f"\n{text_file}"
    )

    print(
        f"\nJSON report:"
        f"\n{json_file}"
    )

    print()

    print(
        "=" * 60
    )


if __name__ == "__main__":
    run()