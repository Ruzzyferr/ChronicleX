from __future__ import annotations

import logging

from modules.publishers.base import PublishResult

logger = logging.getLogger(__name__)


def log_publish_snapshot(results: list[PublishResult], channel_topic: str) -> None:
    for r in results:
        logger.info(
            "analytics publish channel=%s platform=%s success=%s post_id=%s msg=%s dry_run=%s",
            channel_topic,
            r.platform,
            r.success,
            r.post_id,
            (r.message or "")[:120],
            r.dry_run,
        )
