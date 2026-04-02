from __future__ import annotations

import json
import logging

from modules.shared.helpers import source_count
from modules.topic_discovery.adapters.base import DiscoveryAdapter
from modules.topic_discovery.schemas import (
    RawCandidate,
    ScoredCandidate,
    VerificationItem,
    VerificationLLMResponse,
)

logger = logging.getLogger(__name__)


class VerificationService:
    """LLM-backed verification; structural source checks applied locally."""

    def __init__(self, adapter: DiscoveryAdapter) -> None:
        self._adapter = adapter

    def verify_batch(
        self,
        *,
        channel_topic: str,
        candidates: list[RawCandidate],
        min_sources: int,
    ) -> list[ScoredCandidate]:
        if not candidates:
            return []

        serializable = []
        for i, c in enumerate(candidates):
            serializable.append(
                {
                    "index": i,
                    "title": c.title,
                    "summary": c.summary,
                    "event_year": c.event_year,
                    "country": c.country,
                    "sources": [c.source_1, c.source_2, c.source_3],
                }
            )
        payload = json.dumps(serializable, ensure_ascii=False)

        vresp: VerificationLLMResponse = self._adapter.verify_candidates(
            channel_topic=channel_topic,
            candidates_json=payload,
            n_candidates=len(candidates),
        )
        by_index: dict[int, VerificationItem] = {r.index: r for r in vresp.results}

        out: list[ScoredCandidate] = []
        for i, raw in enumerate(candidates):
            src_n = source_count(raw)
            item = by_index.get(i)
            if item is None:
                logger.warning("Missing verification result for index=%s", i)
                vscore, verified = 0, False
            else:
                vscore, verified = item.verification_score, item.is_verified

            if src_n < min_sources:
                verified = False
                vscore = min(vscore, 4)
                logger.info(
                    "Structural reject (sources=%s < %s): %r",
                    src_n,
                    min_sources,
                    raw.title,
                )

            out.append(
                ScoredCandidate(
                    raw=raw,
                    novelty_score=0,
                    verification_score=vscore,
                    is_verified=verified,
                )
            )
        return out
