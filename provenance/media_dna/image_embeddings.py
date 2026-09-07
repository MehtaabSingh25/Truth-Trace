import os

import numpy as np


_PROCESSOR = None
_MODEL = None
_MODEL_NAME = "openai/clip-vit-base-patch32"


def _load_model():
    global _PROCESSOR, _MODEL
    if _PROCESSOR is None or _MODEL is None:
        from transformers import CLIPModel, CLIPProcessor

        model_name = os.environ.get("TRUTH_TRACE_IMAGE_EMBEDDING_MODEL", _MODEL_NAME)
        _PROCESSOR = CLIPProcessor.from_pretrained(model_name)
        _MODEL = CLIPModel.from_pretrained(model_name)
        _MODEL.eval()
    return _PROCESSOR, _MODEL


def extract_image_embedding(image):
    processor, model = _load_model()
    import torch

    inputs = processor(images=image, return_tensors="pt")
    with torch.no_grad():
        embedding = model.get_image_features(**inputs)
    if hasattr(embedding, "pooler_output"):
        embedding = embedding.pooler_output
    vector = embedding[0].cpu().numpy().astype(np.float32).reshape(-1)
    norm = np.linalg.norm(vector)
    if norm == 0:
        raise RuntimeError("Image embedding model returned a zero vector.")
    return (vector / norm).round(8).tolist()


def embedding_status():
    return {
        "model": os.environ.get("TRUTH_TRACE_IMAGE_EMBEDDING_MODEL", _MODEL_NAME),
        "model_available": _MODEL is not None,
    }
