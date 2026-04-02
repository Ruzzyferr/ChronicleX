"""Tests for topic_discovery.schemas — scoring, defaults, validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from modules.topic_discovery.schemas import (
    DiscoveryLLMResponse,
    RawCandidate,
    ScoredCandidate,
    VerificationItem,
)


def test_raw_candidate_defaults():
    c = RawCandidate(title="X")
    assert c.shock_score == 5
    assert c.fear_score == 5
    assert c.clarity_score == 5
    assert c.visual_score == 5
    assert c.summary == ""
    assert c.event_year is None


def test_raw_candidate_score_too_high():
    with pytest.raises(ValidationError):
        RawCandidate(title="X", shock_score=11)


def test_raw_candidate_score_too_low():
    with pytest.raises(ValidationError):
        RawCandidate(title="X", fear_score=-1)


def test_composite_score_all_tens():
    sc = ScoredCandidate(
        raw=RawCandidate(
            title="X",
            shock_score=10,
            fear_score=10,
            clarity_score=10,
            visual_score=10,
        ),
        novelty_score=10,
        verification_score=10,
    )
    assert sc.composite_score() == pytest.approx(10.0)


def test_composite_score_all_zeros():
    sc = ScoredCandidate(
        raw=RawCandidate(
            title="X",
            shock_score=0,
            fear_score=0,
            clarity_score=0,
            visual_score=0,
        ),
        novelty_score=0,
        verification_score=0,
    )
    assert sc.composite_score() == pytest.approx(0.0)


def test_composite_score_weights_sum_to_one():
    assert pytest.approx(0.22 + 0.10 + 0.18 + 0.18 + 0.17 + 0.15) == 1.0


def test_composite_score_specific_case():
    sc = ScoredCandidate(
        raw=RawCandidate(
            title="X",
            shock_score=8,
            fear_score=6,
            clarity_score=7,
            visual_score=9,
        ),
        novelty_score=9,
        verification_score=7,
    )
    expected = 0.22 * 8 + 0.10 * 6 + 0.18 * 7 + 0.18 * 9 + 0.17 * 9 + 0.15 * 7
    assert sc.composite_score() == pytest.approx(expected)


def test_verification_item_index_nonneg():
    with pytest.raises(ValidationError):
        VerificationItem(index=-1, verification_score=5, is_verified=True)


def test_discovery_llm_response_empty():
    r = DiscoveryLLMResponse()
    assert r.candidates == []


def test_scored_candidate_model_copy_preserves():
    sc = ScoredCandidate(
        raw=RawCandidate(title="X", shock_score=8),
        novelty_score=5,
        verification_score=7,
    )
    updated = sc.model_copy(update={"novelty_score": 9})
    assert updated.novelty_score == 9
    assert updated.verification_score == 7
    assert updated.raw.shock_score == 8
