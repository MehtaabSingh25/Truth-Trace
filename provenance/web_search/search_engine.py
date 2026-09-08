import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image
from bs4 import BeautifulSoup


SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
SERPAPI_IMAGE_ENDPOINT = "https://serpapi.com/image"

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}
DEFAULT_FRAME_FRACTIONS = (0.10, 0.30, 0.50, 0.70, 0.90)
MAX_UPLOAD_BYTES = 500_000
REQUEST_TIMEOUT = 25


def _api_key():
    return os.getenv("SERPAPI_KEY") or os.getenv("SERPAPI_API_KEY")


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

    raise RuntimeError(f"{name} is required for video web provenance search.")


def _video_duration(path):
    result = subprocess.run(
        [
            _ffmpeg_tool("ffprobe"), "-v", "error", "-print_format", "json",
            "-show_format", "-show_streams", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    return float(data.get("format", {}).get("duration", 0) or 0)


def _extract_video_frame(path, timestamp):
    fd, name = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    frame_path = Path(name)

    command = [
        _ffmpeg_tool("ffmpeg"), "-y", "-ss", str(timestamp), "-i", str(path),
        "-frames:v", "1", "-q:v", "4", str(frame_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        if not frame_path.exists() or not frame_path.stat().st_size:
            raise RuntimeError("FFmpeg produced no frame.")
        return frame_path
    except Exception:
        frame_path.unlink(missing_ok=True)
        raise


def _prepare_image(path):
    """Return a temporary JPG <= 500 KB for SerpApi Image API."""
    source = Path(path)
    fd, name = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    output = Path(name)

    with Image.open(source) as image:
        image = image.convert("RGB")
        max_side = 1800
        if max(image.size) > max_side:
            scale = max_side / max(image.size)
            image = image.resize(
                (max(1, int(image.width * scale)), max(1, int(image.height * scale))),
                Image.Resampling.LANCZOS,
            )

        quality = 88
        while quality >= 45:
            image.save(output, "JPEG", quality=quality, optimize=True)
            if output.stat().st_size <= MAX_UPLOAD_BYTES:
                return output
            quality -= 7

        # Final size fallback.
        image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
        image.save(output, "JPEG", quality=40, optimize=True)
        if output.stat().st_size > MAX_UPLOAD_BYTES:
            output.unlink(missing_ok=True)
            raise RuntimeError("Could not compress frame below SerpApi's 500 KB upload limit.")

    return output


def _upload_image(path, api_key):
    with open(path, "rb") as handle:
        response = requests.post(
            SERPAPI_IMAGE_ENDPOINT,
            files={"image": (Path(path).name, handle, "image/jpeg")},
            data={"api_key": api_key},
            timeout=REQUEST_TIMEOUT,
        )
    response.raise_for_status()
    data = response.json()
    if data.get("error"):
        raise RuntimeError(data["error"])
    return data["image_id"]


def _lens_search(image_id, api_key, search_type):
    response = requests.get(
        SERPAPI_ENDPOINT,
        params={
            "engine": "google_lens",
            "image_id": image_id,
            "type": search_type,
            "api_key": api_key,
            "hl": "en",
            "gl": "in",
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("error"):
        raise RuntimeError(data["error"])
    return data


def _pick_results(data, search_type):
    keys = {
        "exact_matches": ("exact_matches", "visual_matches"),
        "visual_matches": ("visual_matches", "exact_matches"),
    }[search_type]

    for key in keys:
        values = data.get(key)
        if isinstance(values, list):
            return values, key
    return [], None


def _normalize_result(item, frame_index, search_type):
    link = item.get("link") or item.get("source") or item.get("url")
    title = item.get("title") or item.get("snippet") or "Untitled result"
    source = item.get("source")
    parsed = urlparse(link or "")
    return {
        "title": title,
        "url": link,
        "source": source or parsed.netloc or "Unknown source",
        "thumbnail": item.get("thumbnail") or item.get("image"),
        "snippet": item.get("snippet"),
        "date_from_search": item.get("date"),
        "match_type": search_type,
        "frame_index": frame_index,
    }


def _page_date(url):
    if not url or not url.startswith(("http://", "https://")):
        return {"status": "not_checked"}

    try:
        response = requests.get(
            url,
            timeout=12,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; TruthTrace/1.0; "
                    "+https://example.invalid/truth-trace)"
                )
            },
            allow_redirects=True,
        )
        if response.status_code in {401, 403}:
            return {
                "status": "blocked",
                "http_status": response.status_code,
                "final_url": response.url,
            }
        if response.status_code >= 400:
            return {
                "status": "unavailable",
                "http_status": response.status_code,
                "final_url": response.url,
            }

        soup = BeautifulSoup(response.text, "html.parser")
        candidates = []

        for attrs in [
            {"property": "article:published_time"},
            {"property": "og:article:published_time"},
            {"name": "datePublished"},
            {"name": "date"},
            {"name": "publish-date"},
            {"itemprop": "datePublished"},
        ]:
            tag = soup.find("meta", attrs=attrs)
            if tag and tag.get("content"):
                candidates.append(tag["content"])

        time_tag = soup.find("time")
        if time_tag:
            candidates.append(time_tag.get("datetime") or time_tag.get_text(" ", strip=True))

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                payload = json.loads(script.string or script.get_text())
            except (ValueError, TypeError):
                continue

            def walk(value):
                if isinstance(value, dict):
                    for key in ("datePublished", "dateCreated", "uploadDate"):
                        if value.get(key):
                            candidates.append(str(value[key]))
                    for child in value.values():
                        walk(child)
                elif isinstance(value, list):
                    for child in value:
                        walk(child)

            walk(payload)

        date_value = next((value for value in candidates if value), None)
        return {
            "status": "accessible",
            "http_status": response.status_code,
            "final_url": response.url,
            "published_date": date_value,
        }
    except requests.RequestException as error:
        return {"status": "unavailable", "error": str(error)}
    except Exception as error:
        return {"status": "parse_error", "error": str(error)}


def _dedupe(results):
    merged = {}
    for item in results:
        key = item.get("url") or f"{item.get('title')}|{item.get('source')}"
        if not key:
            continue
        if key not in merged:
            merged[key] = item
        else:
            current = merged[key]
            frames = set(current.get("frame_indices", []))
            frames.update(item.get("frame_indices", [item.get("frame_index")]))
            current["frame_indices"] = sorted(x for x in frames if x is not None)
            if current.get("match_type") != "exact_matches" and item.get("match_type") == "exact_matches":
                current["match_type"] = "exact_matches"
    return list(merged.values())


def search_image(path, frame_index=0):
    api_key = _api_key()
    if not api_key:
        return {
            "status": "not_configured",
            "message": "Set SERPAPI_KEY to enable public-web reverse image search.",
            "results": [],
        }

    prepared = None
    try:
        prepared = _prepare_image(path)
        image_id = _upload_image(prepared, api_key)

        raw_results = []
        for search_type in ("exact_matches", "visual_matches"):
            data = _lens_search(image_id, api_key, search_type)
            values, actual_type = _pick_results(data, search_type)
            for value in values[:10]:
                raw_results.append(
                    _normalize_result(value, frame_index, actual_type or search_type)
                )

        results = _dedupe(raw_results)
        for item in results[:10]:
            item["page"] = _page_date(item["url"])

        return {
            "status": "available",
            "engine": "Google Lens via SerpApi",
            "image_id": image_id,
            "results": results[:20],
        }
    except requests.RequestException as error:
        return {"status": "error", "error": str(error), "results": []}
    except Exception as error:
        return {"status": "error", "error": str(error), "results": []}
    finally:
        if prepared:
            prepared.unlink(missing_ok=True)


def _video_frames(path, max_frames=5):
    duration = _video_duration(path)
    if duration <= 0:
        return []

    fractions = DEFAULT_FRAME_FRACTIONS[:max_frames]
    frames = []
    for index, fraction in enumerate(fractions):
        timestamp = min(duration - 0.05, max(0.0, duration * fraction))
        try:
            frame = _extract_video_frame(path, timestamp)
            frames.append({
                "frame_index": index + 1,
                "timestamp_seconds": round(timestamp, 3),
                "path": frame,
            })
        except Exception as error:
            frames.append({
                "frame_index": index + 1,
                "timestamp_seconds": round(timestamp, 3),
                "error": str(error),
            })
    return frames


def search_video(path, max_frames=5):
    api_key = _api_key()
    if not api_key:
        return {
            "status": "not_configured",
            "message": "Set SERPAPI_KEY to enable public-web reverse image search.",
            "frames": [],
            "results": [],
        }

    frame_records = _video_frames(path, max_frames=max_frames)
    all_results = []
    for frame in frame_records:
        if not frame.get("path"):
            continue
        try:
            frame_result = search_image(frame["path"], frame["frame_index"])
            frame["search_status"] = frame_result.get("status")
            frame["result_count"] = len(frame_result.get("results", []))
            for result in frame_result.get("results", []):
                result["timestamp_seconds"] = frame["timestamp_seconds"]
                all_results.append(result)
        finally:
            frame["path"].unlink(missing_ok=True)

    results = _dedupe(all_results)
    for item in results[:12]:
        item["page"] = _page_date(item["url"])

    return {
        "status": "available",
        "engine": "Google Lens via SerpApi",
        "frame_count": len([frame for frame in frame_records if frame.get("path") is not None]),
        "frames": [
            {
                "frame_index": frame["frame_index"],
                "timestamp_seconds": frame["timestamp_seconds"],
                "search_status": frame.get("search_status"),
                "result_count": frame.get("result_count", 0),
                "error": frame.get("error"),
            }
            for frame in frame_records
        ],
        "results": results[:30],
    }


def search_public_web(path):
    """Search public web evidence without bypassing authentication or private pages."""
    suffix = Path(path).suffix.lower()
    if suffix in VIDEO_EXTENSIONS:
        result = search_video(path)
    else:
        result = search_image(path)

    # Add a simple evidence summary for the API/frontend.
    results = result.get("results", [])
    domains = sorted({
        urlparse(item["url"]).netloc
        for item in results
        if item.get("url")
    })
    result["summary"] = {
        "sources_found": len(results),
        "unique_domains": len(domains),
        "domains": domains[:30],
        "exact_matches": sum(
            1 for item in results if item.get("match_type") == "exact_matches"
        ),
        "accessible_pages": sum(
            1 for item in results
            if item.get("page", {}).get("status") == "accessible"
        ),
        "blocked_pages": sum(
            1 for item in results
            if item.get("page", {}).get("status") == "blocked"
        ),
    }
    return result
