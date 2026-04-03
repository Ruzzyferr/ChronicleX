from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from core.media_models import Scene, ScenesLLMResponse
from modules.scripting.scene_prompts import SCENES_SYSTEM, SCENES_USER_TEMPLATE

logger = logging.getLogger(__name__)

TARGET_TOTAL_MIN = 40.0
TARGET_TOTAL_MAX = 65.0
TARGET_TOTAL_IDEAL = 50.0


def _clamp_duration(d: float) -> float:
    return max(3.0, min(10.0, float(d)))


def normalize_scenes(raw: list[Scene]) -> list[Scene]:
    if len(raw) < 6 or len(raw) > 10:
        raise ValueError(f"Expected 6-10 scenes, got {len(raw)}")
    clamped = [s.model_copy(update={"duration": _clamp_duration(s.duration)}) for s in raw]
    total = sum(s.duration for s in clamped)
    if total < TARGET_TOTAL_MIN or total > TARGET_TOTAL_MAX:
        factor = TARGET_TOTAL_IDEAL / max(total, 0.01)
        adjusted: list[Scene] = []
        for s in clamped:
            new_d = _clamp_duration(s.duration * factor)
            adjusted.append(s.model_copy(update={"duration": new_d}))
        total2 = sum(s.duration for s in adjusted)
        if total2 < TARGET_TOTAL_MIN or total2 > TARGET_TOTAL_MAX:
            factor2 = max(TARGET_TOTAL_MIN, min(TARGET_TOTAL_MAX, total2)) / max(total2, 0.01)
            adjusted = [
                s.model_copy(update={"duration": _clamp_duration(s.duration * factor2)})
                for s in adjusted
            ]
        clamped = adjusted
    return [s.model_copy(update={"scene_id": i}) for i, s in enumerate(clamped, start=1)]


@retry(
    wait=wait_exponential_jitter(initial=1, max=20),
    stop=stop_after_attempt(3),
    reraise=True,
)
def generate_scenes(
    *,
    script: str,
    api_key: str,
    model: str,
    temperature: float = 0.0,
) -> list[Scene]:
    text = script.strip()
    if not text:
        raise ValueError("script is empty")
    client = OpenAI(api_key=api_key)
    user = SCENES_USER_TEMPLATE.format(script=text)
    logger.info("Scene generation: model=%s script_chars=%s", model, len(text))
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SCENES_SYSTEM},
            {"role": "user", "content": user},
        ],
    )
    content = resp.choices[0].message.content or "{}"
    data: dict[str, Any] = json.loads(content)
    parsed = ScenesLLMResponse.model_validate(data)
    scenes = normalize_scenes(parsed.scenes)
    logger.info("Scene generation done: %s scenes, total ~%.1fs", len(scenes), sum(s.duration for s in scenes))
    return scenes
