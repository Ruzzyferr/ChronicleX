from __future__ import annotations

import logging
from pathlib import Path

from openai import OpenAI

logger = logging.getLogger(__name__)


def transcribe_with_word_timestamps(
    audio_path: Path,
    api_key: str,
    language: str = "tr",
) -> list[dict]:
    """Return Whisper word-level timestamps, or [] on failure."""
    if not api_key.strip():
        return []
    if not audio_path.is_file():
        return []

    try:
        client = OpenAI(api_key=api_key)
        with audio_path.open("rb") as audio_file:
            resp = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["word"],
                language=language,
            )
    except Exception as exc:
        logger.warning("Whisper transcription failed: %s", exc)
        return []

    words_raw = getattr(resp, "words", None)
    if not isinstance(words_raw, list):
        return []

    words: list[dict] = []
    for item in words_raw:
        try:
            word = str(getattr(item, "word", "")).strip()
            start = float(getattr(item, "start", 0.0))
            end = float(getattr(item, "end", start))
        except (TypeError, ValueError):
            continue
        if not word:
            continue
        if end < start:
            end = start
        words.append({"word": word, "start": start, "end": end})
    return words
