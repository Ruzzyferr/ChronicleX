from __future__ import annotations

import logging
import re
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


def _image_url(item: dict) -> str:
    for key in ("src", "imageUrl", "image_url", "url"):
        value = item.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value
    return ""


def _compact_query(query: str, max_words: int = 12, max_chars: int = 140) -> str:
    """Reduce long DALL-E style prompts into Lexica-friendly short queries."""
    q = query.strip().lower()
    q = re.sub(r"[^\w\s-]", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    if not q:
        return ""
    words = q.split(" ")
    short = " ".join(words[:max_words]).strip()
    if len(short) > max_chars:
        short = short[:max_chars].rstrip()
    return short


def search_and_download(
    query: str,
    output_path: Path,
    width: int = 1024,
    height: int = 1792,
) -> bool:
    """Search Lexica and download the best matching (prefer vertical) image."""
    q = query.strip()
    if not q:
        return False
    q_short = _compact_query(q)
    candidates = [q]
    if q_short and q_short != q:
        candidates.insert(0, q_short)

    payload = None
    headers = {"User-Agent": "ChronicleX/1.0", "Accept": "application/json"}
    for q_try in candidates:
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
                resp = client.get(
                    "https://lexica.art/api/v1/search",
                    params={"q": q_try},
                )
                resp.raise_for_status()
                payload = resp.json()
                break
        except Exception as exc:
            logger.warning("Lexica search failed for query '%s': %s", q_try, exc)
            continue
    if not isinstance(payload, dict):
        return False

    images = payload.get("images", [])
    if not isinstance(images, list) or not images:
        return False

    target_ratio = width / max(height, 1)
    best_url = ""
    best_score = -10**9
    for item in images:
        if not isinstance(item, dict):
            continue
        url = _image_url(item)
        if not url:
            continue
        w = item.get("width") or 0
        h = item.get("height") or 0
        try:
            w_f = float(w)
            h_f = float(h)
        except (TypeError, ValueError):
            w_f, h_f = 0.0, 0.0
        ratio = (w_f / h_f) if h_f > 0 else 0.0
        is_vertical = h_f > w_f if (w_f > 0 and h_f > 0) else False
        # Prefer vertical results and closer aspect ratio.
        score = (1000 if is_vertical else 0) - abs(ratio - target_ratio) * 100
        if score > best_score:
            best_score = score
            best_url = url

    if not best_url:
        return False

    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            img_resp = client.get(best_url)
            img_resp.raise_for_status()
            content = img_resp.content
        if len(content) < 256:
            return False
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(content)
        return True
    except Exception as exc:
        logger.warning("Lexica image download failed: %s", exc)
        return False
