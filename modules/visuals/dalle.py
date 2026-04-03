from __future__ import annotations

import base64
import hashlib
import logging
from pathlib import Path

import httpx
from openai import BadRequestError, OpenAI

logger = logging.getLogger(__name__)

# Ana prompt sonuna: şiddet/mood kelimelerinden kaçın (DALL·E politikası)
STYLE_SUFFIX = (
    ", vertical 9:16 digital illustration, stylized historical animation art style, "
    "dramatic cinematic lighting, rich saturated colors, bold composition, "
    "detailed scene depicting the narrated event, high production value, "
    "no text, no watermark, no logos"
)

# Politika reddinde dönüşümlü güvenli sahneler (konu metninden bağımsız)
_FALLBACK_EN = [
    "Digital illustration of a grand imperial palace at sunset, vermilion walls glowing "
    "in golden light, dramatic sky, stylized animation art, sweeping cinematic composition",
    "Stylized illustration of a scholar's study, warm candlelight casting long shadows, "
    "silk scrolls and ink brushes on wooden desk, rich warm color palette, detailed scene",
    "Illustrated ancient parchment world map with ornate compass rose, dramatic lighting, "
    "aged texture, rich sepia and gold tones, cinematic top-down view",
    "Digital art of bronze ritual vessels in dramatic spotlight, deep shadows, "
    "rich metallic reflections, stylized historical illustration, moody atmosphere",
    "Stylized illustration of a classical garden at twilight, moonlight on lotus pond, "
    "covered walkway silhouette, rich blue and purple palette, atmospheric depth",
    "Illustrated close-up of ancient bamboo manuscript slips, dramatic side lighting, "
    "aged textures, warm amber tones, stylized documentary illustration",
]


def _is_image_policy_error(exc: BaseException) -> bool:
    s = str(exc).lower()
    if "content_policy" in s or "safety system" in s or "image_generation_user_error" in s:
        return True
    if isinstance(exc, BadRequestError):
        body = getattr(exc, "body", None)
        if isinstance(body, dict):
            err = body.get("error") or {}
            if err.get("code") == "content_policy_violation":
                return True
    return False


def _download_or_decode(item, output_path: Path) -> None:
    if item.url:
        r = httpx.get(item.url, timeout=120.0)
        r.raise_for_status()
        output_path.write_bytes(r.content)
    elif item.b64_json:
        output_path.write_bytes(base64.standard_b64decode(item.b64_json))
    else:
        raise RuntimeError("DALL-E response had no url or b64_json")


def _images_generate(
    *,
    client: OpenAI,
    model: str,
    full_prompt: str,
    size: str,
    output_path: Path,
) -> None:
    result = client.images.generate(
        model=model,
        prompt=full_prompt[:3900],
        size=size,
        quality="standard",
        n=1,
    )
    _download_or_decode(result.data[0], output_path)


def generate_image(
    *,
    prompt: str,
    output_path: Path,
    api_key: str,
    model: str = "dall-e-3",
    size: str = "1024x1792",
) -> None:
    """DALL·E görseli; içerik politikası reddinde güvenli yedek sahneler dener."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    client = OpenAI(api_key=api_key)

    base = prompt.strip()
    primary = (base + STYLE_SUFFIX)[:3900]

    h = int(hashlib.md5(str(output_path).encode("utf-8", errors="replace")).hexdigest(), 16)
    fallbacks = [_FALLBACK_EN[(h + i) % len(_FALLBACK_EN)] + STYLE_SUFFIX for i in range(len(_FALLBACK_EN))]

    attempts: list[tuple[str, str]] = [("primary", primary)]
    for i, fb in enumerate(fallbacks):
        attempts.append((f"fallback_{i + 1}", fb[:3900]))

    last_exc: BaseException | None = None
    for label, prompt_body in attempts:
        try:
            logger.info("DALL-E: %s -> %s", label, output_path.name)
            _images_generate(
                client=client,
                model=model,
                full_prompt=prompt_body,
                size=size,
                output_path=output_path,
            )
            logger.info("DALL-E saved %s bytes -> %s", output_path.stat().st_size, output_path)
            return
        except BadRequestError as e:
            last_exc = e
            if _is_image_policy_error(e):
                logger.warning(
                    "DALL-E politika reddi (%s), sonraki görsel denemesi: %s",
                    output_path.name,
                    label,
                )
                continue
            raise

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("DALL-E: no attempts made")
