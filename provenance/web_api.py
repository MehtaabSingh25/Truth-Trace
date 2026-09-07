import hashlib
import json
import shutil
import sys
import uuid
from pathlib import Path

import requests
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "media_dna"))
from media_features import analyze_media


UPLOAD_DIR = BASE_DIR / "web_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
FRONTEND_DIR = BASE_DIR / "frontend"
ALLOWED = {".jpg", ".jpeg", ".jpe", ".png", ".webp", ".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}
PLATFORMS = {
    "InstaMock": "http://127.0.0.1:8000",
    "XMock": "http://127.0.0.1:8001",
    "FaceMock": "http://127.0.0.1:8002",
}
PROPAGATION_DIR = (
    BASE_DIR.parent / "internet" / "propagation_simulator" / "outputs"
)

app = FastAPI(title="Truth Trace Provenance API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


@app.get("/")
def root():
    return {"service": "provenance", "status": "online"}


def _load_lineage(posts, target_hash):
    exact_posts = [
        post for post in posts
        if post.get("exact_hash_match")
        and post.get("media_sha256") == target_hash
    ]
    if not exact_posts:
        return None

    post_keys = {(post["platform"], str(post["post_id"])) for post in posts}
    exact_post_keys = {
        (post["platform"], str(post["post_id"]))
        for post in exact_posts
    }
    candidates = []
    if PROPAGATION_DIR.is_dir():
        for manifest_path in PROPAGATION_DIR.glob("*_propagation.json"):
            try:
                manifest = manifest_path.read_text(encoding="utf-8")
                data = json.loads(manifest)
            except (OSError, ValueError):
                continue
            matched_events = [
                event for event in data.get("events", [])
                if (event.get("platform"), str(event.get("post_id"))) in post_keys
            ]
            if matched_events:
                exact_events = [
                    event for event in matched_events
                    if (
                        (event.get("platform"), str(event.get("post_id")))
                        in exact_post_keys
                        and event.get("output", {}).get("sha256") == target_hash
                    )
                ]
                if exact_events:
                    candidates.append((data, matched_events, exact_events))
    if not candidates:
        return None
    data, matched_events, exact_events = max(
        candidates,
        key=lambda item: (len(item[2]), len(item[1])),
    )
    return {
        "media_id": data.get("media_id"),
        "origin": data.get("original"),
        "scenario": data.get("scenario"),
        "events": data.get("events", []),
        "matched_event_ids": [event["event_id"] for event in matched_events],
        "target_event_ids": [event["event_id"] for event in exact_events],
    }


def _trace_platforms(target):
    target_hash = hashlib.sha256(target.read_bytes()).hexdigest()
    trace = []
    all_posts = []
    for platform, base_url in PLATFORMS.items():
        platform_result = {"platform": platform, "status": "available", "posts": []}
        try:
            response = requests.get(f"{base_url}/api/posts", timeout=10)
            response.raise_for_status()
            for post in response.json():
                media_url = post.get("media_url")
                if not media_url:
                    continue
                media_response = requests.get(
                    f"{base_url}{media_url}", timeout=10
                )
                media_response.raise_for_status()
                media_hash = hashlib.sha256(media_response.content).hexdigest()
                traced_post = {
                    "platform": platform,
                    "post_id": post.get("id"),
                    "username": post.get("username"),
                    "caption": post.get("caption", post.get("text", "")),
                    "created_at": post.get("created_at"),
                    "media_type": post.get("media_type"),
                    "media_url": f"{base_url}{media_url}",
                    "media_sha256": media_hash,
                    "exact_hash_match": media_hash == target_hash,
                }
                platform_result["posts"].append(traced_post)
                all_posts.append(traced_post)
        except requests.RequestException as error:
            platform_result["status"] = "unavailable"
            platform_result["error"] = str(error)
        trace.append(platform_result)
    return {
        "target_sha256": target_hash,
        "platforms": trace,
        "lineage": _load_lineage(all_posts, target_hash),
    }


@app.post("/api/analyze")
def analyze(media: UploadFile = File(...)):
    suffix = Path(media.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(status_code=415, detail="Unsupported media format")
    target = UPLOAD_DIR / f"{uuid.uuid4()}{suffix}"
    with target.open("wb") as destination:
        shutil.copyfileobj(media.file, destination)
    result = analyze_media(target)
    result["uploaded_filename"] = media.filename
    result["platform_trace"] = _trace_platforms(target)
    return result
