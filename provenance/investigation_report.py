from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse


def _parse_date(value):
    if not value:
        return None
    text = str(value).strip()
    candidates = [text, text.replace("Z", "+00:00")]
    for candidate in candidates:
        try:
            return datetime.fromisoformat(candidate).replace(tzinfo=None)
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:10], fmt)
        except ValueError:
            pass
    return None


def build_final_report(data):
    ai = data.get("ai_assessment") or data.get("video_analysis", {}).get("ai_assessment") or {}
    ai_label = ai.get("label", "authentic_unknown")
    ai_score = float(ai.get("confidence", ai.get("artificial_score", 0)) or 0)
    if data.get("media_type") == "video":
        ai_score = float(data.get("video_analysis", {}).get("ai_assessment", {}).get("artificial_score", ai_score) or ai_score)

    web = data.get("web_trace") or {}
    web_results = web.get("results") or []
    platforms = data.get("platform_trace", {}).get("platforms") or []
    platform_matches = []
    for platform in platforms:
        for post in platform.get("posts") or []:
            if post.get("exact_hash_match"):
                platform_matches.append({
                    "source_type": "simulated_platform",
                    "source": platform.get("platform"),
                    "title": post.get("caption") or "Exact media match",
                    "url": post.get("media_url"),
                    "date": post.get("created_at"),
                    "match_type": "exact_hash_match",
                    "accessible": True,
                })

    web_history = []
    for item in web_results:
        page = item.get("page") or {}
        date = page.get("published_date") or item.get("date_from_search")
        web_history.append({
            "source_type": "public_web",
            "source": item.get("source") or (urlparse(item.get("url") or "").netloc),
            "title": item.get("title"),
            "url": item.get("url"),
            "date": date,
            "match_type": item.get("match_type"),
            "accessible": page.get("status") == "accessible",
            "page_status": page.get("status"),
            "frame_index": item.get("frame_index"),
            "timestamp_seconds": item.get("timestamp_seconds"),
        })

    history = web_history + platform_matches
    dated = [x for x in history if _parse_date(x.get("date"))]
    dated.sort(key=lambda x: _parse_date(x.get("date")))
    earliest = dated[0] if dated else None

    exact_web = sum(1 for x in web_history if x.get("match_type") == "exact_matches")
    visual_web = sum(1 for x in web_history if x.get("match_type") == "visual_matches")
    exact_platform = len(platform_matches)
    accessible_web = sum(1 for x in web_history if x.get("accessible"))

    evidence_reasons = []
    if ai_label == "ai_generated" and ai_score >= 0.5:
        evidence_reasons.append(f"AI detector classified the media as AI-generated with a {ai_score:.0%} model score.")
    elif ai.get("model_available") is False:
        evidence_reasons.append("AI detector was unavailable; the verdict does not treat AI classification as evidence.")
    else:
        evidence_reasons.append("AI detector did not provide strong evidence of AI generation.")
    if exact_web:
        evidence_reasons.append(f"Public-web reverse search returned {exact_web} exact match result(s).")
    if visual_web:
        evidence_reasons.append(f"Public-web reverse search returned {visual_web} visual match result(s).")
    if exact_platform:
        evidence_reasons.append(f"The simulated platform feeds contain {exact_platform} exact media hash match(es), providing propagation evidence.")
    if earliest:
        evidence_reasons.append(f"The earliest dated source observed by the system is {earliest.get('source')} on {earliest.get('date')}.")
    if not history:
        evidence_reasons.append("No dated public or simulated-platform source evidence was established.")

    if ai_label == "ai_generated" and ai_score >= 0.75:
        verdict = "Likely AI-generated media"
        verdict_class = "likely_ai"
    elif ai_label == "ai_generated" and ai_score >= 0.5:
        verdict = "Possibly AI-generated; manual review recommended"
        verdict_class = "review"
    elif exact_web or exact_platform:
        verdict = "Authenticity unresolved; provenance evidence found"
        verdict_class = "provenance_found"
    else:
        verdict = "No strong evidence of AI generation or propagation established"
        verdict_class = "inconclusive"

    if history:
        confidence = min(0.99, 0.55 + (0.20 if exact_web else 0) + (0.15 if exact_platform else 0) + (0.10 if earliest else 0))
        if verdict_class in {"likely_ai", "review"}:
            confidence = min(0.99, max(ai_score, confidence))
    else:
        confidence = ai_score if ai.get("model_available") else 0.0

    return {
        "verdict": verdict,
        "verdict_class": verdict_class,
        "confidence": round(confidence, 4),
        "ai_detection": {
            "label": ai_label,
            "score": round(ai_score, 4),
            "model": ai.get("model"),
            "method": ai.get("method"),
            "model_available": ai.get("model_available"),
        },
        "earliest_observed_source": earliest,
        "source_history": dated,
        "propagation": {
            "simulated_platform_matches": exact_platform,
            "public_web_exact_matches": exact_web,
            "public_web_visual_matches": visual_web,
            "events": history,
        },
        "evidence_reasons": evidence_reasons,
        "limitations": [
            "An earliest observed public source is not proof of the original creator.",
            "AI detection is probabilistic and should be considered alongside forensic and provenance evidence.",
            "Private, login-only, or blocked pages are not bypassed.",
            "Public-web search coverage depends on the reverse-search provider and indexed content available at investigation time.",
        ],
        "report_title": "Truth Trace Final Investigation Report",
    }
