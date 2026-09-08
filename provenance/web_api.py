import hashlib
import json
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from PIL import Image
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "media_dna"))
from media_features import analyze_media
from web_search.search_engine import search_public_web
from investigation_report import build_final_report


UPLOAD_DIR = BASE_DIR / "web_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_DIR = BASE_DIR / "history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_MEDIA_DIR = HISTORY_DIR / "media"
HISTORY_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
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
app.mount("/history/media", StaticFiles(directory=HISTORY_MEDIA_DIR), name="history-media")


@app.get("/")
def root():
    return {"service": "provenance", "status": "online"}


# ---------------------------------------------------------------------------
# Investigation history
#
# Every completed analysis is written to disk as its own JSON record plus a
# thumbnail copy of the evidence file, so past investigations can be listed
# and re-opened later (the "history" feature the frontend previously had no
# way to show, since nothing was ever persisted).
# ---------------------------------------------------------------------------

def _save_history_record(result, target, uploaded_filename):
    record_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    thumb_path = None
    try:
        suffix = target.suffix.lower()
        thumb_name = f"{record_id}{suffix}"
        shutil.copyfile(target, HISTORY_MEDIA_DIR / thumb_name)
        thumb_path = f"/history/media/{thumb_name}"
    except Exception:
        thumb_path = None

    final_report = result.get("final_report") or {}
    record = {
        "id": record_id,
        "created_at": created_at,
        "uploaded_filename": uploaded_filename,
        "media_type": result.get("media_type"),
        "sha256": result.get("sha256"),
        "thumbnail_url": thumb_path,
        "verdict": final_report.get("verdict"),
        "verdict_class": final_report.get("verdict_class"),
        "confidence": final_report.get("confidence"),
        "result": result,
    }
    (HISTORY_DIR / f"{record_id}.json").write_text(
        json.dumps(record, indent=2, default=str), encoding="utf-8"
    )
    return record


def _history_summary(record):
    return {
        "id": record.get("id"),
        "created_at": record.get("created_at"),
        "uploaded_filename": record.get("uploaded_filename"),
        "media_type": record.get("media_type"),
        "sha256": record.get("sha256"),
        "thumbnail_url": record.get("thumbnail_url"),
        "verdict": record.get("verdict"),
        "verdict_class": record.get("verdict_class"),
        "confidence": record.get("confidence"),
    }


@app.get("/api/history")
def list_history(limit: int = 50):
    records = []
    for path in HISTORY_DIR.glob("*.json"):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    records.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return [_history_summary(record) for record in records[: max(1, min(limit, 200))]]


@app.get("/api/history/{record_id}")
def get_history_record(record_id: str):
    path = HISTORY_DIR / f"{record_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Investigation not found.")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=500, detail=f"Could not read investigation: {error}") from error
    return record.get("result", record)


@app.delete("/api/history/{record_id}")
def delete_history_record(record_id: str):
    path = HISTORY_DIR / f"{record_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Investigation not found.")
    record = json.loads(path.read_text(encoding="utf-8"))
    thumbnail = record.get("thumbnail_url")
    path.unlink(missing_ok=True)
    if thumbnail:
        thumb_file = HISTORY_MEDIA_DIR / Path(thumbnail).name
        thumb_file.unlink(missing_ok=True)
    return {"status": "deleted", "id": record_id}


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


def _is_public_http_url(value):
    try:
        parsed = requests.utils.urlparse(value)
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _download_public_image(url):
    if not _is_public_http_url(url):
        raise HTTPException(status_code=400, detail="Enter a valid public http(s) image URL.")
    parsed = requests.utils.urlparse(url)
    host = parsed.hostname or ""
    if host.lower() in {"localhost", "127.0.0.1", "::1"} or host.startswith("10.") or host.startswith("192.168."):
        raise HTTPException(status_code=400, detail="Private/local URLs are not allowed.")
    try:
        response = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 TruthTrace/1.0"}, stream=True)
        response.raise_for_status()
    except requests.RequestException as error:
        raise HTTPException(status_code=502, detail=f"Could not fetch the public image URL: {error}") from error
    content_type = (response.headers.get("content-type") or "").lower()
    suffix = Path(parsed.path).suffix.lower()
    if not suffix or suffix not in ALLOWED:
        suffix = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/jpg": ".jpg"}.get(content_type, ".jpg")
    if not content_type.startswith("image/") and suffix not in {".jpg", ".jpeg", ".jpe", ".png", ".webp"}:
        raise HTTPException(status_code=415, detail="The URL does not appear to point to a supported image.")
    target = UPLOAD_DIR / f"{uuid.uuid4()}{suffix}"
    total = 0
    try:
        with target.open("wb") as destination:
            for chunk in response.iter_content(chunk_size=1024 * 128):
                if not chunk:
                    continue
                total += len(chunk)
                if total > 25 * 1024 * 1024:
                    raise HTTPException(status_code=413, detail="Remote image is larger than 25 MB.")
                destination.write(chunk)
        with Image.open(target) as image:
            image.verify()
    except HTTPException:
        target.unlink(missing_ok=True)
        raise
    except Exception as error:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=415, detail=f"Could not decode the remote image: {error}") from error
    return target


def _complete_analysis(target, uploaded_filename):
    result = analyze_media(target)
    result["uploaded_filename"] = uploaded_filename
    result["platform_trace"] = _trace_platforms(target)
    try:
        result["web_trace"] = search_public_web(target)
    except Exception as error:
        result["web_trace"] = {
            "status": "error", "error": str(error), "results": [],
            "summary": {"sources_found": 0, "unique_domains": 0, "domains": [], "exact_matches": 0, "accessible_pages": 0, "blocked_pages": 0},
        }
    result["final_report"] = build_final_report(result)
    return result


@app.post("/api/analyze")
def analyze(media: UploadFile = File(...)):
    suffix = Path(media.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(status_code=415, detail="Unsupported media format")
    target = UPLOAD_DIR / f"{uuid.uuid4()}{suffix}"
    with target.open("wb") as destination:
        shutil.copyfileobj(media.file, destination)
    result = _complete_analysis(target, media.filename or target.name)
    record = _save_history_record(result, target, media.filename or target.name)
    result["history_id"] = record["id"]
    return result


@app.post("/api/analyze-url")
def analyze_url(image_url: str = Form(...)):
    target = _download_public_image(image_url.strip())
    try:
        result = _complete_analysis(target, image_url.strip())
        record = _save_history_record(result, target, image_url.strip())
        result["history_id"] = record["id"]
        return result
    finally:
        target.unlink(missing_ok=True)
