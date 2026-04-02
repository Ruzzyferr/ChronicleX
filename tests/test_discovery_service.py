"""Tests for discovery service — pick_winner, to_topic_row, pipeline."""

from __future__ import annotations

import pytest

from modules.shared.helpers import century, hook_pattern, source_count
from modules.topic_discovery.schemas import (
    DiscoveryLLMResponse,
    RawCandidate,
    ScoredCandidate,
    VerificationItem,
    VerificationLLMResponse,
)
from modules.topic_discovery.service import _pick_winner, _to_topic_row, run_discovery_pipeline
from core.models import TopicConfig
from app.settings import Settings
from storage.models import TopicRow


# --- helpers ---


def _scored(title="X", shock=7, fear=5, clarity=7, visual=7,
            novelty=9, verif=8, verified=True, **kw) -> ScoredCandidate:
    raw_kw = dict(
        title=title, summary="x", shock_score=shock, fear_score=fear,
        clarity_score=clarity, visual_score=visual,
        source_1="S1", source_2="S2",
    )
    raw_kw.update(kw)
    return ScoredCandidate(
        raw=RawCandidate(**raw_kw),
        novelty_score=novelty,
        verification_score=verif,
        is_verified=verified,
    )


# --- _pick_winner ---


def test_pick_winner_selects_highest_composite():
    a = _scored(title="Low", shock=3, novelty=3, verif=8)
    b = _scored(title="High", shock=10, novelty=10, verif=9)
    winner = _pick_winner([a, b], min_verification=7)
    assert winner is not None
    assert winner.raw.title == "High"


def test_pick_winner_soft_fallback():
    # Not verified, but has 2+ sources and verif >= max(5, 7-2)=5
    a = _scored(title="Soft", verif=6, verified=False)
    winner = _pick_winner([a], min_verification=7)
    assert winner is not None
    assert winner.raw.title == "Soft"


def test_pick_winner_returns_none():
    a = _scored(title="Bad", verif=2, verified=False, source_1=None, source_2=None)
    winner = _pick_winner([a], min_verification=7)
    assert winner is None


def test_pick_winner_empty_list():
    assert _pick_winner([], min_verification=7) is None


# --- _to_topic_row ---


def test_to_topic_row_maps_fields():
    sc = _scored(
        title="Test Title",
        shock=8, fear=6, clarity=7, visual=9,
        novelty=8, verif=7, verified=True,
    )
    sc.raw.country = "TR"
    sc.raw.event_year = 1900
    sc.raw.category = "war"
    row = _to_topic_row("channel", sc)
    assert row.title == "Test Title"
    assert row.channel_topic == "channel"
    assert row.shock_score == 8
    assert row.novelty_score == 8
    assert row.verification_score == 7
    assert row.is_verified is True
    assert row.ready_for_script is False
    assert row.is_used is False


# --- shared helpers ---


def test_source_count_with_values():
    c = RawCandidate(title="X", source_1="a", source_2="b", source_3="c")
    assert source_count(c) == 3


def test_source_count_empty_strings():
    c = RawCandidate(title="X", source_1="", source_2="  ", source_3=None)
    assert source_count(c) == 0


def test_century_various():
    assert century(None) is None
    assert century(0) is None
    assert century(-5) is None
    assert century(1) == 1
    assert century(100) == 1
    assert century(101) == 2
    assert century(2000) == 20
    assert century(2001) == 21


def test_hook_pattern_truncation():
    long_title = "A" * 100
    hp = hook_pattern(long_title)
    assert len(hp) == 40


# --- run_discovery_pipeline (integration with mock) ---


class _FakeAdapter:
    def __init__(self, candidates: list[RawCandidate], verif_items: list[VerificationItem]):
        self._candidates = candidates
        self._verif_items = verif_items

    def generate_candidates(self, *, channel_topic, language, count_min, count_max):
        return DiscoveryLLMResponse(candidates=self._candidates)

    def verify_candidates(self, *, channel_topic, candidates_json, n_candidates):
        return VerificationLLMResponse(results=self._verif_items)


def _make_candidates(n: int) -> list[RawCandidate]:
    return [
        RawCandidate(
            title=f"Topic {i}",
            summary=f"Summary {i}",
            event_year=1800 + i,
            country=f"Country{i}",
            category=f"cat{i % 5}",
            source_1=f"src1_{i}",
            source_2=f"src2_{i}",
            shock_score=7,
            fear_score=5,
            clarity_score=7,
            visual_score=7,
        )
        for i in range(n)
    ]


def _make_verif_items(n: int) -> list[VerificationItem]:
    return [
        VerificationItem(index=i, verification_score=8, is_verified=True)
        for i in range(n)
    ]


def test_pipeline_happy_path(db_session):
    candidates = _make_candidates(12)
    verif_items = _make_verif_items(12)
    adapter = _FakeAdapter(candidates, verif_items)

    topic_config = TopicConfig(topic_name="test_channel", language="tr")
    settings = Settings(database_url="sqlite:///:memory:", dry_run=False)

    detail = run_discovery_pipeline(db_session, settings, topic_config, adapter)
    assert detail["generated"] == 12
    assert detail["chosen_topic_id"] is not None
    assert len(detail["topic_ids"]) > 0


def test_pipeline_too_few_candidates(db_session):
    candidates = _make_candidates(5)  # less than 10
    adapter = _FakeAdapter(candidates, [])

    topic_config = TopicConfig(topic_name="test_channel", language="tr")
    settings = Settings(database_url="sqlite:///:memory:", dry_run=False)

    with pytest.raises(ValueError, match="at least 10"):
        run_discovery_pipeline(db_session, settings, topic_config, adapter)
