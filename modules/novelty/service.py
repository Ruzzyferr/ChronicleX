from __future__ import annotations

import logging

from modules.novelty.rules import EditorialSnapshot, evaluate_novelty
from modules.topic_discovery.schemas import RawCandidate

logger = logging.getLogger(__name__)


class NoveltyService:
    def filter_candidates(
        self, candidates: list[RawCandidate], memory: EditorialSnapshot
    ) -> list[tuple[RawCandidate, int, str]]:
        """Return list of (candidate, novelty_score, reason) that pass gates."""
        kept: list[tuple[RawCandidate, int, str]] = []
        for c in candidates:
            ok, score, reason = evaluate_novelty(c, memory)
            if not ok:
                logger.info("Novelty reject title=%r reason=%s", c.title, reason)
                continue
            kept.append((c, score, reason))
        logger.info("Novelty kept %s / %s candidates", len(kept), len(candidates))
        return kept
