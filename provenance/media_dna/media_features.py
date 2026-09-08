import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
import numpy as np

from PIL import Image
import imagehash

from dna_extractor import calculate_sha256, calculate_color_histogram


VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}


def _ffmpeg_tool(name):
    executable = shutil.which(name)
    if executable:
        return executable

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        package_root = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        matches = sorted(package_root.glob(f"Gyan.FFmpeg_*/*/bin/{name}.exe"))
        if matches:
            return str(matches[-1])

    raise RuntimeError(
        f"{name} is required for video provenance analysis but was not found."
    )


def _ffprobe(path):
    result = subprocess.run(
        [
            _ffmpeg_tool("ffprobe"), "-v", "error", "-print_format", "json",
            "-show_format", "-show_streams", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _frame_at(path, timestamp):
    temporary = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    temporary.close()
    frame_path = Path(temporary.name)
    commands = [
        [
            _ffmpeg_tool("ffmpeg"), "-y", "-ss", str(timestamp), "-i", str(path),
            "-frames:v", "1", "-c:v", "png", str(frame_path),
        ],
        [
            _ffmpeg_tool("ffmpeg"), "-y", "-i", str(path), "-ss", str(timestamp),
            "-frames:v", "1", "-c:v", "png", str(frame_path),
        ],
    ]
    errors = []
    for command in commands:
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
            if frame_path.exists() and frame_path.stat().st_size:
                return frame_path
            errors.append("FFmpeg completed without writing a frame")
            frame_path.unlink(missing_ok=True)
        except subprocess.CalledProcessError as error:
            errors.append(error.stderr.strip() or str(error))
            frame_path.unlink(missing_ok=True)
    raise RuntimeError(
        f"FFmpeg could not extract frame at {timestamp:.3f}s: "
        f"{' | '.join(errors)}"
    )


def analyze_media(file_path):
    path = Path(file_path)
    if path.suffix.lower() not in VIDEO_EXTENSIONS:
        with Image.open(path) as image:
            result = {
                "media_type": "image",
                "sha256": calculate_sha256(path),
                "file": str(path),
                "file_size_bytes": path.stat().st_size,
                "format": image.format,
                "mode": image.mode,
                "width": image.width,
                "height": image.height,
                "aspect_ratio": round(image.width / image.height, 6) if image.height else None,
                "perceptual_hash": {
                    "phash": str(imagehash.phash(image)),
                    "dhash": str(imagehash.dhash(image)),
                    "ahash": str(imagehash.average_hash(image)),
                },
                "color_histogram": calculate_color_histogram(image),
            }
            try:
                from image_embeddings import extract_image_embedding
                result["image_embedding"] = {
                    "model": "openai/clip-vit-base-patch32",
                    "vector": extract_image_embedding(image),
                }
            except (ImportError, OSError, RuntimeError) as error:
                result["image_embedding"] = {
                    "model": "openai/clip-vit-base-patch32",
                    "available": False,
                    "error": str(error),
                }
        from image_forensics import analyze_image_forensics
        result.update(analyze_image_forensics(path))
        # Image AI assessment was previously only applied to video frames.
        # Keep every existing forensic result and add the image-level detector.
        try:
            from image_ai_assessment import assess_image_ai_likelihood
            result["ai_assessment"] = assess_image_ai_likelihood(path)
        except (ImportError, OSError, RuntimeError) as error:
            result["ai_assessment"] = {
                "label": "authentic_unknown",
                "confidence": 0.0,
                "method": "model_unavailable",
                "model_available": False,
                "error": str(error),
                "disclaimer": "AI classification could not be completed.",
            }
        return result

    metadata = _ffprobe(path)
    stream = next(
        item for item in metadata.get("streams", [])
        if item.get("codec_type") == "video"
    )
    duration = float(metadata.get("format", {}).get("duration", 0) or 0)
    last_timestamp = max(0.0, duration - min(0.5, duration / 4))
    timestamps = sorted({0.0, max(0.0, duration / 2), last_timestamp})
    frames = []
    frame_extraction_errors = []
    try:
        for timestamp in timestamps:
            try:
                frame_path = _frame_at(path, timestamp)
            except RuntimeError as error:
                frame_extraction_errors.append(str(error))
                if frames:
                    continue
                raise
            with Image.open(frame_path) as frame:
                frame_record = {
                    "timestamp_seconds": timestamp,
                    "phash": str(imagehash.phash(frame)),
                    "dhash": str(imagehash.dhash(frame)),
                    "ahash": str(imagehash.average_hash(frame)),
                    "histogram": calculate_color_histogram(frame),
                }
                try:
                    from image_forensics import _face_analysis
                    frame_record["face_analysis"] = _face_analysis(frame)
                except (ImportError, OSError, RuntimeError) as error:
                    frame_record["face_analysis"] = {
                        "status": "unavailable",
                        "error": str(error),
                    }
                try:
                    from image_ai_assessment import assess_image_ai_likelihood
                    frame_record["ai_assessment"] = (
                        assess_image_ai_likelihood(frame_path)
                    )
                except (ImportError, OSError, RuntimeError) as error:
                    frame_record["ai_assessment"] = {
                        "label": "authentic_unknown",
                        "confidence": 0.0,
                        "method": "unavailable",
                        "model_available": False,
                        "error": str(error),
                    }
                try:
                    from image_embeddings import extract_image_embedding
                    frame_record["image_embedding"] = {
                        "model": "openai/clip-vit-base-patch32",
                        "vector": extract_image_embedding(frame.copy()),
                    }
                except (ImportError, OSError, RuntimeError) as error:
                    frame_record["image_embedding"] = {
                        "available": False,
                        "error": str(error),
                    }
                frames.append(frame_record)
            frame_path.unlink(missing_ok=True)
    finally:
        if "frame_path" in locals():
            frame_path.unlink(missing_ok=True)

    representative = frames[len(frames) // 2]
    ai_frames = [
        frame["ai_assessment"]
        for frame in frames
        if frame.get("ai_assessment", {}).get("model_available")
    ]
    artificial_scores = [
        max(
            (
                prediction["score"]
                for prediction in frame.get("ai_assessment", {}).get(
                    "raw_predictions", []
                )
                if "artificial" in prediction["label"].lower()
            ),
            default=0.0,
        )
        for frame in frames
    ]
    ai_frame_count = sum(score >= 0.5 for score in artificial_scores)
    embedding_vectors = [
        frame["image_embedding"]["vector"]
        for frame in frames
        if frame.get("image_embedding", {}).get("vector")
    ]
    temporal_scores = []
    for previous, current in zip(frames, frames[1:]):
        similarity = sum(
            a == b
            for a, b in zip(
                previous["phash"],
                current["phash"],
            )
        ) / len(previous["phash"])
        temporal_scores.append(round(similarity, 6))
    mean_embedding = []
    if embedding_vectors:
        mean_embedding = np.mean(
            np.asarray(embedding_vectors, dtype=np.float32),
            axis=0,
        )
        norm = np.linalg.norm(mean_embedding)
        if norm:
            mean_embedding = (mean_embedding / norm).round(8).tolist()
        else:
            mean_embedding = []
    return {
        "media_type": "video",
        "sha256": calculate_sha256(path),
        "file": str(path),
        "file_size_bytes": path.stat().st_size,
        "format": path.suffix.lstrip(".").upper(),
        "codec": stream.get("codec_name"),
        "duration_seconds": duration,
        "frame_rate": stream.get("r_frame_rate"),
        "width": stream.get("width"),
        "height": stream.get("height"),
        "aspect_ratio": round(stream["width"] / stream["height"], 6)
        if stream.get("height") else None,
        "frame_count": stream.get("nb_frames"),
        "sampled_frames": frames,
        "image_embedding": {
            "model": "openai/clip-vit-base-patch32",
            "vector": mean_embedding,
            "source": "mean_sampled_frame_embedding",
        },
        "video_analysis": {
            "frame_count_analyzed": len(frames),
            "frame_extraction_errors": frame_extraction_errors,
            "ai_assessment": {
                "frames_with_model": len(ai_frames),
                "artificial_score": round(
                    sum(artificial_scores) / len(artificial_scores), 6
                ) if artificial_scores else 0.0,
                "ai_frame_consensus": round(
                    ai_frame_count / len(artificial_scores), 6
                ) if artificial_scores else 0.0,
                "label": (
                    "ai_generated"
                    if artificial_scores
                    and sum(artificial_scores) / len(artificial_scores) >= 0.5
                    else "authentic_unknown"
                ),
            },
            "face_summary": {
                "faces_per_frame": [
                    frame.get("face_analysis", {}).get("face_count", 0)
                    for frame in frames
                ],
                "max_faces": max(
                    (
                        frame.get("face_analysis", {}).get("face_count", 0)
                        for frame in frames
                    ),
                    default=0,
                ),
            },
            "embedding": {
                "model": "openai/clip-vit-base-patch32",
                "frame_embeddings": len(embedding_vectors),
                "dimensions": len(embedding_vectors[0])
                if embedding_vectors else 0,
            },
            "temporal_consistency": {
                "adjacent_phash_similarity": temporal_scores,
                "mean_adjacent_similarity": round(
                    sum(temporal_scores) / len(temporal_scores), 6
                ) if temporal_scores else 0.0,
                "status": (
                    "review_required"
                    if temporal_scores
                    and sum(temporal_scores) / len(temporal_scores) < 0.2
                    else "screening_only"
                ),
            },
        },
        "perceptual_hash": {
            "phash": representative["phash"],
            "dhash": representative["dhash"],
            "ahash": representative["ahash"],
        },
        "color_histogram": representative["histogram"],
    }
