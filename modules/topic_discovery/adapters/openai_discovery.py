from __future__ import annotations

import json
import logging

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from modules.topic_discovery.prompts import (
    DISCOVERY_SYSTEM,
    DISCOVERY_USER_TEMPLATE,
)
from modules.verification.prompts import (
    VERIFICATION_SYSTEM,
    VERIFICATION_USER_TEMPLATE,
)
from modules.topic_discovery.schemas import DiscoveryLLMResponse, VerificationLLMResponse

logger = logging.getLogger(__name__)


class OpenAIDiscoveryAdapter:
    def __init__(self, *, api_key: str, model: str) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model

    @retry(
        wait=wait_exponential_jitter(initial=1, max=20),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def generate_candidates(
        self,
        *,
        channel_topic: str,
        language: str,
        count_min: int,
        count_max: int,
    ) -> DiscoveryLLMResponse:
        user = DISCOVERY_USER_TEMPLATE.format(
            channel_topic=channel_topic,
            language=language,
            count_min=count_min,
            count_max=count_max,
        )
        logger.info(
            "OpenAI discovery request model=%s count=%s-%s",
            self._model,
            count_min,
            count_max,
        )
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": DISCOVERY_SYSTEM},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.error("Discovery LLM returned invalid JSON (len=%d): %.500s", len(content), content)
            raise
        parsed = DiscoveryLLMResponse.model_validate(data)
        logger.info("OpenAI discovery received %s candidates", len(parsed.candidates))
        return parsed

    @retry(
        wait=wait_exponential_jitter(initial=1, max=20),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def verify_candidates(
        self,
        *,
        channel_topic: str,
        candidates_json: str,
        n_candidates: int,
    ) -> VerificationLLMResponse:
        user = VERIFICATION_USER_TEMPLATE.format(
            channel_topic=channel_topic,
            candidates_json=candidates_json,
            n_minus_one=n_candidates - 1,
        )
        logger.info("OpenAI verification request n=%s", n_candidates)
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": VERIFICATION_SYSTEM},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.error("Verification LLM returned invalid JSON (len=%d): %.500s", len(content), content)
            raise
        parsed = VerificationLLMResponse.model_validate(data)
        logger.info("OpenAI verification received %s results", len(parsed.results))
        return parsed
