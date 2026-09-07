from pathlib import Path
import os

from PIL import Image


_DEFAULT_MODEL = "umm-maybe/AI-image-detector"
_CLASSIFIER = None


def _get_classifier():
    global _CLASSIFIER
    if _CLASSIFIER is None:
        from transformers import pipeline

        _CLASSIFIER = pipeline(
            "image-classification",
            model=os.environ.get("TRUTH_TRACE_IMAGE_AI_MODEL", _DEFAULT_MODEL),
        )
    return _CLASSIFIER


def _result_label(label):
    normalized = label.lower()
    if any(
        token in normalized
        for token in ("fake", "ai", "artificial", "generated", "synthetic")
    ):
        return "ai_generated"
    if any(token in normalized for token in ("real", "authentic", "human")):
        return "authentic_unknown"
    return "authentic_unknown"


def assess_image_ai_likelihood(file_path):
    """Classify an image with a pretrained detector, with explicit availability status."""
    path = Path(file_path)
    with Image.open(path) as image:
        exif = image.getexif()
        software = str(exif.get(305, "")).lower()

        if any(marker in software for marker in ("stable diffusion", "midjourney", "dall-e")):
            return {
                "label": "ai_generated",
                "confidence": 0.95,
                "method": "metadata_screening",
                "model_available": False,
                "signals": ["known_ai_generator_in_software_metadata"],
                "disclaimer": "Metadata evidence can be missing or forged.",
            }

        try:
            predictions = _get_classifier()(image.convert("RGB"), top_k=2)
        except (ImportError, OSError, RuntimeError) as error:
            return {
                "label": "authentic_unknown",
                "confidence": 0.0,
                "method": "model_unavailable",
                "model_available": False,
                "model": os.environ.get("TRUTH_TRACE_IMAGE_AI_MODEL", _DEFAULT_MODEL),
                "signals": [],
                "error": str(error),
                "disclaimer": "AI classification could not be completed.",
            }

    best = max(predictions, key=lambda item: float(item["score"]))
    return {
        "label": _result_label(best["label"]),
        "confidence": round(float(best["score"]), 6),
        "method": "huggingface_image_classification",
        "model_available": True,
        "model": os.environ.get("TRUTH_TRACE_IMAGE_AI_MODEL", _DEFAULT_MODEL),
        "raw_predictions": predictions,
        "signals": [],
        "disclaimer": (
            "This is a probabilistic model result and should be reviewed with "
            "forensic and metadata evidence."
        ),
    }
