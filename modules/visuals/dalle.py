from __future__ import annotations

import logging
from pathlib import Path

import httpx
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

logger = logging.getLogger(__name__)

STYLE_SUFFIX = (
    ", cinematic, dark tone, historical realism, dramatic lighting, fog and shadows, "
    "vertical composition, no text, no watermark"
)


@retry(
    wait=wait_exponential_jitter(initial=1, max=25),
    stop=stop_after_attempt(3),
    reraise=True,
)
def generate_image(
    *,
    prompt: str,
    output_path: Path,
    api_key: str,
    model: str = "dall-e-3",
    size: str = "1024x1792",
) -> None:
    full_prompt = (prompt.strip() + STYLE_SUFFIX)[:3900]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    client = OpenAI(api_key=api_key)
    logger.info("DALL-E: scene image -> %s", output_path.name)
    result = client.images.generate(
        model=model,
        prompt=full_prompt,
        size=size,
        quality="standard",
        n=1,
    )
    item = result.data[0]
    if item.url:
        r = httpx.get(item.url, timeout=120.0)
        r.raise_for_status()
        output_path.write_bytes(r.content)
    elif item.b64_json:
        import base64

        output_path.write_bytes(base64.standard_b64decode(item.b64_json))
    else:
        raise RuntimeError("DALL-E response had no url or b64_json")
    logger.info("DALL-E saved %s bytes -> %s", output_path.stat().st_size, output_path)
