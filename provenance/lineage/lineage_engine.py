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

OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# LOAD LATEST INVESTIGATION
# ---------------------------------------------------------

def get_latest_investigation():
    investigations = [
        path
        for path in MEDIA_DNA_OUTPUT_DIR.iterdir()
        if path.is_dir()
    ]

    if not investigations:
        raise FileNotFoundError(
            "No Media DNA investigation found."
        )

    return max(
        investigations,
        key=lambda path: path.stat().st_mtime
    )


# ---------------------------------------------------------
# LOAD JSON
# ---------------------------------------------------------

def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


# ---------------------------------------------------------
# LOAD MEDIA DNA
# ---------------------------------------------------------

def load_media_dna(investigation_id):

    dna_file = (
        MEDIA_DNA_OUTPUT_DIR /
        investigation_id /
        "media_dna.json"
    )

    if not dna_file.exists():
        raise FileNotFoundError(
            f"Media DNA not found: {dna_file}"
        )

    return load_json(dna_file)


# ---------------------------------------------------------
# LOAD SIMILARITY
# ---------------------------------------------------------

def load_similarity(investigation_id):

    similarity_file = (
        SIMILARITY_OUTPUT_DIR /
        investigation_id /
        "similarity.json"
    )

    if not similarity_file.exists():
        raise FileNotFoundError(
            f"Similarity output not found: {similarity_file}"
        )

    return load_json(similarity_file)


# ---------------------------------------------------------
# LOAD COLLECTOR METADATA
# ---------------------------------------------------------

def load_collector_metadata(investigation_id):

    investigation_dir = (
        COLLECTOR_OUTPUT_DIR /
        investigation_id
    )

    if not investigation_dir.exists():
        raise FileNotFoundError(
            f"Collector investigation not found: {investigation_dir}"
        )

    metadata = {}

    platform_directories = [
        path
        for path in investigation_dir.iterdir()
        if path.is_dir()
    ]

    for platform_dir in platform_directories:

        posts_file = platform_dir / "posts.json"

        if not posts_file.exists():
            continue

        posts = load_json(posts_file)

        for post in posts:

            media_url = post.get("media_url")
            local_file = post.get("local_file")

            if not media_url and not local_file:
                continue

            media_filename = Path(media_url).name if media_url else None
            local_filename = Path(local_file).name if local_file else None
            post_id = post.get("id")
            record = {
                "platform": platform_dir.name,
                "post_id": post_id,
                "username": post.get("username"),
                "created_at": post.get("created_at"),
                "media_url": media_url,
                "media_type": post.get("media_type"),
            }

            # DNA files are stored as post_<id>_<media filename>, while
            # collector posts refer to the platform media filename.
            for filename in {media_filename, local_filename}:
                if filename:
                    metadata[filename] = record
                    metadata[f"post_{post_id}_{filename}"] = record

    return metadata


# ---------------------------------------------------------
# PARSE TIMESTAMP
# ---------------------------------------------------------

def parse_timestamp(value):

    if not value:
        return None

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f"
    ]

    for fmt in formats:

        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass

    return None


# ---------------------------------------------------------
# BUILD ARTIFACT INDEX
# ---------------------------------------------------------

def build_artifact_index(dna_data, collector_metadata):

    artifacts = {}

    for artifact in dna_data.get("artifacts", []):

        artifact_id = artifact["artifact_id"]

        file_path = Path(
            artifact.get("file")
            or artifact.get("source_file")
            or artifact.get("dna", {}).get("file", "")
        )

        filename = file_path.name

        metadata = collector_metadata.get(
            filename,
            {}
        )

        timestamp = parse_timestamp(
            metadata.get("created_at")
        )

        artifacts[artifact_id] = {
            "artifact_id": artifact_id,

            "file": artifact.get("file"),

            "filename": filename,

            "sha256": artifact["dna"].get("sha256"),

            "platform": metadata.get("platform"),

            "post_id": metadata.get("post_id"),

            "username": metadata.get("username"),

            "created_at": metadata.get("created_at"),

            "timestamp": timestamp.isoformat()
            if timestamp
            else None,

            "media_type": metadata.get("media_type"),

            "width": artifact["dna"].get("width"),

            "height": artifact["dna"].get("height"),

            "format": artifact["dna"].get("format")
        }

    return artifacts


# ---------------------------------------------------------
# BUILD SIMILARITY INDEX
# ---------------------------------------------------------

def build_similarity_index(similarity_data):

    index = {}

    for comparison in similarity_data.get(
        "comparisons",
        []
    ):

        artifact_a = comparison["artifact_a"]
        artifact_b = comparison["artifact_b"]

        key = frozenset([
            artifact_a,
            artifact_b
        ])

        index[key] = comparison

    return index


# ---------------------------------------------------------
# PLATFORM ORDER
# ---------------------------------------------------------

PLATFORM_ORDER = {
    "InstaMock": 0,
    "XMock": 1,
    "FaceMock": 2
}


def platform_direction(platform_a, platform_b):

    if not platform_a or not platform_b:
        return None

    if platform_a == platform_b:
        return 0

    a = PLATFORM_ORDER.get(platform_a)
    b = PLATFORM_ORDER.get(platform_b)

    if a is None or b is None:
        return None

    return b - a


# ---------------------------------------------------------
# DETERMINE TEMPORAL ORDER
# ---------------------------------------------------------

def temporal_order(artifact_a, artifact_b):

    timestamp_a = artifact_a.get("timestamp")
    timestamp_b = artifact_b.get("timestamp")

    if not timestamp_a or not timestamp_b:
        return None

    if timestamp_a < timestamp_b:
        return -1

    if timestamp_a > timestamp_b:
        return 1

    return 0


# ---------------------------------------------------------
# EDGE INFERENCE
# ---------------------------------------------------------

def infer_edge(
    artifact_a,
    artifact_b,
    similarity
):

    score = similarity["overall_similarity"]

    exact = similarity["exact_sha256_match"]

    reasons = []

    # Similarity requirement
    if exact:
        similarity_strength = "EXACT"
        reasons.append("exact_sha256_match")

    elif score >= 0.90:
        similarity_strength = "HIGH"
        reasons.append("very_high_media_similarity")

    elif score >= 0.75:
        similarity_strength = "MEDIUM"
        reasons.append("moderate_media_similarity")

    else:
        return None

    # Chronology
    order = temporal_order(
        artifact_a,
        artifact_b
    )

    if order == 0:
        return None

    if order is None:
        return None

    # Determine direction
    if order == -1:
        parent = artifact_a
        child = artifact_b
    else:
        parent = artifact_b
        child = artifact_a

    # Platform evidence
    platform_a = parent.get("platform")
    platform_b = child.get("platform")

    if platform_a and platform_b:

        if platform_a != platform_b:
            reasons.append(
                f"cross_platform:{platform_a}->{platform_b}"
            )

        else:
            reasons.append(
                "same_platform"
            )

    # Dimension evidence
    parent_width = parent.get("width")
    parent_height = parent.get("height")

    child_width = child.get("width")
    child_height = child.get("height")

    if all([
        parent_width,
        parent_height,
        child_width,
        child_height
    ]):

        if (
            child_width <= parent_width
            and child_height <= parent_height
        ):
            reasons.append(
                "child_dimensions_not_larger"
            )

    # Format evidence
    if parent.get("format") != child.get("format"):
        reasons.append(
            "format_changed"
        )

    # Calculate confidence
    confidence_score = score

    if exact:
        confidence_score = min(
            1.0,
            confidence_score + 0.02
        )

    if (
        platform_a
        and platform_b
        and platform_a != platform_b
    ):
        confidence_score += 0.02

    if (
        parent_width
        and parent_height
        and child_width
        and child_height
        and child_width <= parent_width
        and child_height <= parent_height
    ):
        confidence_score += 0.02

    confidence_score = min(
        1.0,
        round(confidence_score, 6)
    )

    if confidence_score >= 0.97:
        confidence = "VERY_HIGH"

    elif confidence_score >= 0.90:
        confidence = "HIGH"

    elif confidence_score >= 0.75:
        confidence = "MEDIUM"

    else:
        confidence = "LOW"

    return {
        "parent": parent["artifact_id"],
        "child": child["artifact_id"],

        "similarity_score": score,

        "confidence_score": confidence_score,

        "confidence": confidence,

        "reasons": reasons,

        "evidence": {
            "exact_sha256_match": exact,

            "parent_platform": parent.get(
                "platform"
            ),

            "child_platform": child.get(
                "platform"
            ),

            "parent_timestamp": parent.get(
                "created_at"
            ),

            "child_timestamp": child.get(
                "created_at"
            ),

            "parent_dimensions": [
                parent.get("width"),
                parent.get("height")
            ],

            "child_dimensions": [
                child.get("width"),
                child.get("height")
            ],

            "parent_format": parent.get(
                "format"
            ),

            "child_format": child.get(
                "format"
            )
        }
    }


# ---------------------------------------------------------
# INFER GRAPH
# ---------------------------------------------------------

def infer_lineage(
    artifacts,
    similarity_index
):

    edges = []

    artifact_list = list(
        artifacts.values()
    )

    for i in range(len(artifact_list)):

        for j in range(
            i + 1,
            len(artifact_list)
        ):

            artifact_a = artifact_list[i]
            artifact_b = artifact_list[j]

            key = frozenset([
                artifact_a["artifact_id"],
                artifact_b["artifact_id"]
            ])

            similarity = similarity_index.get(key)

            if not similarity:
                continue

            edge = infer_edge(
                artifact_a,
                artifact_b,
                similarity
            )

            if edge:
                edges.append(edge)

    return edges


# ---------------------------------------------------------
# BUILD NODES
# ---------------------------------------------------------

def build_nodes(artifacts, edges):

    connected = set()

    for edge in edges:

        connected.add(
            edge["parent"]
        )

        connected.add(
            edge["child"]
        )

    nodes = []

    for artifact_id, artifact in artifacts.items():

        node_type = "isolated"

        if artifact_id in connected:
            node_type = "artifact"

        nodes.append({
            "artifact_id": artifact_id,
            "platform": artifact.get("platform"),
            "post_id": artifact.get("post_id"),
            "username": artifact.get("username"),
            "created_at": artifact.get("created_at"),
            "file": artifact.get("file"),
            "width": artifact.get("width"),
            "height": artifact.get("height"),
            "format": artifact.get("format"),
            "node_type": node_type
        })

    return nodes


# ---------------------------------------------------------
# FIND ROOTS / LEAFS
# ---------------------------------------------------------

def find_roots_and_leaves(nodes, edges):

    node_ids = {
        node["artifact_id"]
        for node in nodes
    }

    parents = {
        edge["parent"]
        for edge in edges
    }

    children = {
        edge["child"]
        for edge in edges
    }

    roots = sorted(
        node_ids - children
    )

    leaves = sorted(
        node_ids - parents
    )

    return roots, leaves


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def run():

    print()
    print("=" * 60)
    print("              TRUTH TRACE LINEAGE")
    print("=" * 60)

    investigation_dir = get_latest_investigation()

    investigation_id = (
        investigation_dir.name
    )

    print(
        f"\nInvestigation: "
        f"{investigation_id}"
    )

    dna_data = load_media_dna(
        investigation_id
    )

    similarity_data = load_similarity(
        investigation_id
    )

    collector_metadata = (
        load_collector_metadata(
            investigation_id
        )
    )

    print(
        f"Media DNA artifacts: "
        f"{len(dna_data.get('artifacts', []))}"
    )

    print(
        f"Similarity comparisons: "
        f"{len(similarity_data.get('comparisons', []))}"
    )

    print(
        f"Collector media records: "
        f"{len(collector_metadata)}"
    )

    artifacts = build_artifact_index(
        dna_data,
        collector_metadata
    )

    similarity_index = (
        build_similarity_index(
            similarity_data
        )
    )

    edges = infer_lineage(
        artifacts,
        similarity_index
    )

    nodes = build_nodes(
        artifacts,
        edges
    )

    roots, leaves = (
        find_roots_and_leaves(
            nodes,
            edges
        )
    )

    output = {

        "investigation_id":
            investigation_id,

        "engine": {
            "name":
                "Truth Trace Lineage Engine",

            "version":
                "1.0"
        },

        "generated_at":
            datetime.now().isoformat(),

        "graph": {

            "node_count":
                len(nodes),

            "edge_count":
                len(edges),

            "nodes":
                nodes,

            "edges":
                edges,

            "roots":
                roots,

            "leaves":
                leaves
        }
    }

    output_dir = (
        OUTPUT_DIR /
        investigation_id
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    output_file = (
        output_dir /
        "lineage.json"
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

    print()
    print("LINEAGE GRAPH")
    print("-" * 60)

    print(
        f"Nodes: {len(nodes)}"
    )

    print(
        f"Inferred edges: {len(edges)}"
    )

    print(
        f"Roots: {len(roots)}"
    )

    print(
        f"Leaves: {len(leaves)}"
    )

    print()

    for edge in edges:

        print(
            f"{edge['parent']} "
            f"--> "
            f"{edge['child']}"
        )

        print(
            f"  Similarity: "
            f"{edge['similarity_score']}"
        )

        print(
            f"  Confidence: "
            f"{edge['confidence']}"
        )

        print(
            f"  Reasons: "
            f"{', '.join(edge['reasons'])}"
        )

        print()

    print("=" * 60)
    print("              LINEAGE COMPLETE")
    print("=" * 60)

    print(
        f"\nOutput: "
        f"{output_file}"
    )

    print()


if __name__ == "__main__":
    run()