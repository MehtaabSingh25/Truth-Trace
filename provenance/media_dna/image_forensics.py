from pathlib import Path
import io

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageEnhance


_FACE_CASCADE = cv2.CascadeClassifier(
    str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
)


def _face_analysis(image):
    rgb = np.asarray(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    faces = _FACE_CASCADE.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(30, 30),
    )
    return {
        "detector": "opencv_haar_frontalface_default",
        "face_count": len(faces),
        "faces": [
            {
                "x": int(x),
                "y": int(y),
                "width": int(width),
                "height": int(height),
                "confidence": None,
            }
            for x, y, width, height in faces
        ],
        "status": "detected" if len(faces) else "not_detected",
    }


def _ela_analysis(image):
    if image.format not in {"JPEG", "WEBP"}:
        return {
            "available": False,
            "reason": "ELA is implemented for JPEG and WEBP images.",
        }

    original = image.convert("RGB")
    encoded = io.BytesIO()
    original.save(encoded, format="JPEG", quality=90)
    encoded.seek(0)
    recompressed = Image.open(encoded).convert("RGB")
    difference = ImageChops.difference(original, recompressed)
    enhanced = ImageEnhance.Brightness(difference).enhance(10)
    values = np.asarray(enhanced, dtype=np.float32)
    mean_error = float(values.mean())
    max_error = float(values.max())
    return {
        "available": True,
        "recompression_quality": 90,
        "mean_error": round(mean_error, 4),
        "max_error": round(max_error, 4),
        "interpretation": (
            "uniform_recompression_error"
            if mean_error < 12
            else "non_uniform_recompression_error"
        ),
    }


def _pixel_statistics(image):
    grayscale = np.asarray(image.convert("L"), dtype=np.float32)
    noise = cv2.Laplacian(grayscale, cv2.CV_32F).var()
    return {
        "laplacian_variance": round(float(noise), 4),
        "edge_density": round(
            float(np.count_nonzero(cv2.Canny(grayscale.astype(np.uint8), 100, 200)))
            / grayscale.size,
            6,
        ),
    }


def _copy_move_analysis(image):
    gray = np.asarray(image.convert("L"))
    if min(gray.shape) < 64:
        return {
            "available": False,
            "status": "insufficient_image_size",
            "match_count": 0,
            "suspicious_regions": [],
        }

    orb = cv2.ORB_create(nfeatures=1200)
    keypoints, descriptors = orb.detectAndCompute(gray, None)
    if descriptors is None or len(keypoints) < 8:
        return {
            "available": True,
            "status": "not_detected",
            "match_count": 0,
            "suspicious_regions": [],
        }

    matches = []
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    distances = matcher.knnMatch(descriptors, descriptors, k=min(8, len(descriptors)))
    for query_index, candidates in enumerate(distances):
        candidates = [
            candidate
            for candidate in candidates
            if candidate.trainIdx != query_index
        ]
        if len(candidates) < 2:
            continue
        first, second = candidates[0], candidates[1]
        if first.distance < 0.7 * second.distance:
            source = keypoints[first.queryIdx].pt
            target = keypoints[first.trainIdx].pt
            if abs(source[0] - target[0]) + abs(source[1] - target[1]) > 24:
                matches.append(first)

    offset_groups = {}
    for match in matches:
        source_x, source_y = keypoints[match.queryIdx].pt
        target_x, target_y = keypoints[match.trainIdx].pt
        offset = (
            round((target_x - source_x) / 8),
            round((target_y - source_y) / 8),
        )
        offset_groups.setdefault(offset, []).append(match)

    strongest_group = max(offset_groups.values(), key=len, default=[])
    regions = []
    for match in strongest_group[:20]:
        x, y = keypoints[match.trainIdx].pt
        regions.append({
            "x": round(float(x), 2),
            "y": round(float(y), 2),
            "radius": 16,
        })
    return {
        "available": True,
        "status": "possible_copy_move" if len(strongest_group) >= 6 else "not_detected",
        "match_count": len(strongest_group),
        "suspicious_regions": regions,
        "disclaimer": "Feature matches are screening signals, not proof of forgery.",
    }


def analyze_image_forensics(file_path):
    path = Path(file_path)
    from image_ai_assessment import assess_image_ai_likelihood

    with Image.open(path) as image:
        exif = {
            str(key): str(value)
            for key, value in image.getexif().items()
        }
        return {
            "ai_assessment": assess_image_ai_likelihood(path),
            "face_analysis": _face_analysis(image),
            "forgery_analysis": {
                "ela": _ela_analysis(image),
                "pixel_statistics": _pixel_statistics(image),
                "copy_move": _copy_move_analysis(image),
                "status": "screening_only",
                "disclaimer": (
                    "These signals identify possible editing inconsistencies; "
                    "they are not proof of manipulation."
                ),
            },
            "metadata": {
                "exif": exif,
                "software": exif.get("305"),
                "camera_make": exif.get("271"),
                "camera_model": exif.get("272"),
                "timestamp": exif.get("306"),
            },
            "transformation_analysis": {
                "format": image.format,
                "dimensions": {"width": image.width, "height": image.height},
                "has_exif": bool(exif),
                "signals": [
                    "recompression_screening_available"
                    if image.format in {"JPEG", "WEBP"}
                    else "format_metadata_only"
                ],
            },
        }
