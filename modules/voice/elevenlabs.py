from __future__ import annotations

import logging
from pathlib import Path

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

logger = logging.getLogger(__name__)


@retry(
    wait=wait_exponential_jitter(initial=1, max=20),
    stop=stop_after_attempt(3),
    reraise=True,
)
def generate_voice_mp3(
    *,
    script: str,
    output_path: Path,
    api_key: str,
    voice_id: str,
    model_id: str = "eleven_multilingual_v2",
) -> None:
    text = script.strip()
    if not text:
        raise ValueError("script is empty")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    body = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.55,
            "similarity_boost": 0.75,
            "style": 0.2,
            "use_speaker_boost": True,
        },
    }
    logger.info("ElevenLabs TTS: chars=%s -> %s", len(text), output_path.name)
    with httpx.Client(timeout=180.0) as client:
        r = client.post(url, headers=headers, json=body)
        r.raise_for_status()
        output_path.write_bytes(r.content)
    logger.info("Voice saved %s bytes", output_path.stat().st_size)
