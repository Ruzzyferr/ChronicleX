from __future__ import annotations

from typing import Protocol

from modules.topic_discovery.schemas import DiscoveryLLMResponse, VerificationLLMResponse


class DiscoveryAdapter(Protocol):
    def generate_candidates(
        self,
        *,
        channel_topic: str,
        language: str,
        count_min: int,
        count_max: int,
    ) -> DiscoveryLLMResponse: ...

    def verify_candidates(
        self,
        *,
        channel_topic: str,
        candidates_json: str,
        n_candidates: int,
    ) -> VerificationLLMResponse: ...
