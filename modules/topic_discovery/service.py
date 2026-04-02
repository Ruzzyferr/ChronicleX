from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.settings import Settings
from core.models import TopicConfig
from modules.novelty.rules import snapshot_from_row
from modules.novelty.service import NoveltyService
from modules.shared.helpers import century, hook_pattern, source_count
from modules.topic_discovery.adapters.base import DiscoveryAdapter
from modules.topic_discovery.schemas import RawCandidate, ScoredCandidate
from modules.verification.service import VerificationService
from storage.models import TopicRow
from storage.repositories import editorial_memory as em_repo
from storage.repositories import job_runs as job_repo
from storage.repositories import topics as topics_repo

logger = logging.getLogger(__name__)

COUNT_MIN = 12
COUNT_MAX = 22


def _to_topic_row(channel_topic: str, sc: ScoredCandidate) -> TopicRow:
    r = sc.raw
    return TopicRow(
        channel_topic=channel_topic,
        title=r.title,
        summary=r.summary or "",
        event_year=r.event_year,
        country=r.country,
        region=r.region,
        category=r.category,
        subcategory=r.subcategory,
        people_involved=r.people_involved,
        source_count=source_count(r),
        source_1=r.source_1,
        source_2=r.source_2,
        source_3=r.source_3,
        shock_score=r.shock_score,
        fear_score=r.fear_score,
        clarity_score=r.clarity_score,
        visual_score=r.visual_score,
        novelty_score=sc.novelty_score,
        verification_score=sc.verification_score,
        is_verified=sc.is_verified,
        is_used=False,
        ready_for_script=False,
    )


def _pick_winner(
    scored: list[ScoredCandidate], min_verification: int
) -> ScoredCandidate | None:
    eligible = [
        s
        for s in scored
        if s.is_verified and s.verification_score >= min_verification
    ]
    if eligible:
        return max(eligible, key=lambda s: s.composite_score())
    soft = [
        s
        for s in scored
        if source_count(s.raw) >= 2 and s.verification_score >= max(5, min_verification - 2)
    ]
    if soft:
        logger.warning(
            "No fully verified winner; using soft fallback among %s candidates",
            len(soft),
        )
        return max(soft, key=lambda s: s.composite_score())
    return None


def run_discovery_pipeline(
    session: Session,
    _settings: Settings,
    topic_config: TopicConfig,
    adapter: DiscoveryAdapter,
) -> dict[str, Any]:
    channel = topic_config.topic_name
    job = None
    try:
        job = job_repo.start_job(
            session,
            "discovery",
            {"channel_topic": channel, "language": topic_config.language},
        )
        disc = adapter.generate_candidates(
            channel_topic=channel,
            language=topic_config.language,
            count_min=COUNT_MIN,
            count_max=COUNT_MAX,
        )
        raw_list = disc.candidates
        if len(raw_list) < 10:
            raise ValueError(
                f"Discovery returned only {len(raw_list)} candidates; need at least 10"
            )

        mem_row = em_repo.get_or_create(session, channel)
        snap = snapshot_from_row(mem_row)
        novelty = NoveltyService()
        kept = novelty.filter_candidates(raw_list, snap)
        if not kept:
            raise ValueError("Novelty filter removed all candidates; broaden prompts or clear memory")

        raws = [t[0] for t in kept]
        novelty_scores = [t[1] for t in kept]

        verifier = VerificationService(adapter)
        verified_list = verifier.verify_batch(
            channel_topic=channel,
            candidates=raws,
            min_sources=topic_config.content_rules.min_sources,
        )

        scored: list[ScoredCandidate] = []
        for i, sc in enumerate(verified_list):
            nov = novelty_scores[i] if i < len(novelty_scores) else 0
            scored.append(sc.model_copy(update={"novelty_score": nov}))

        min_v = topic_config.content_rules.minimum_verification_score
        winner = _pick_winner(scored, min_v)

        topic_ids: list[int] = []
        id_by_candidate: dict[int, int] = {}
        for i, sc in enumerate(scored):
            if topics_repo.title_exists(session, channel, sc.raw.title):
                logger.info("Skipping duplicate title in DB: %r", sc.raw.title)
                continue
            row = _to_topic_row(channel, sc)
            topics_repo.insert_topic(session, row)
            topic_ids.append(row.id)
            id_by_candidate[i] = row.id

        winner_id: int | None = None
        if winner is not None:
            try:
                win_idx = scored.index(winner)
            except ValueError:
                win_idx = -1
            if win_idx >= 0:
                winner_id = id_by_candidate[win_idx]
                topics_repo.set_ready_for_script(session, winner_id, channel)
                em_repo.update_after_selection(
                    session,
                    channel,
                    title=winner.raw.title,
                    country=winner.raw.country,
                    century=century(winner.raw.event_year),
                    category=winner.raw.category,
                    people=winner.raw.people_involved,
                    hook_pattern=hook_pattern(winner.raw.title),
                )

        detail = {
            "job_id": job.id,
            "generated": len(raw_list),
            "after_novelty": len(scored),
            "topic_ids": topic_ids,
            "chosen_topic_id": winner_id,
        }
        job_repo.complete_job(session, job.id, detail)
        logger.info("Discovery complete: %s", detail)
        return detail
    except Exception as exc:
        if job is not None:
            try:
                session.rollback()
                job_repo.fail_job(session, job.id, str(exc))
                session.commit()
            except Exception:
                logger.warning("Could not record job failure for job_id=%s", job.id)
        raise
