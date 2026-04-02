"""Tests for verification service with mock adapter."""

from __future__ import annotations

import logging

from modules.topic_discovery.schemas import (
    RawCandidate,
    VerificationItem,
    VerificationLLMResponse,
)
from modules.verification.service import VerificationService


class FakeAdapter:
    """Minimal adapter for testing verification."""

    def __init__(self, results: list[VerificationItem] | None = None):
        self._results = results or []

    def generate_candidates(self, **kw):
        raise NotImplementedError

    def verify_candidates(self, *, channel_topic, candidates_json, n_candidates):
        return VerificationLLMResponse(results=self._results)


def _candidate(**kw) -> RawCandidate:
    defaults = dict(
        title="Test", summary="x",
        source_1="Src A", source_2="Src B",
        shock_score=7, fear_score=5, clarity_score=7, visual_score=7,
    )
    defaults.update(kw)
    return RawCandidate(**defaults)


def test_verify_batch_empty():
    svc = VerificationService(FakeAdapter())
    assert svc.verify_batch(channel_topic="t", candidates=[], min_sources=2) == []


def test_verify_batch_all_verified():
    items = [
        VerificationItem(index=0, verification_score=8, is_verified=True),
        VerificationItem(index=1, verification_score=9, is_verified=True),
    ]
    svc = VerificationService(FakeAdapter(items))
    candidates = [_candidate(title="A"), _candidate(title="B")]
    result = svc.verify_batch(channel_topic="t", candidates=candidates, min_sources=2)
    assert len(result) == 2
    assert result[0].is_verified is True
    assert result[0].verification_score == 8
    assert result[1].verification_score == 9


def test_verify_batch_structural_reject_low_sources():
    items = [
        VerificationItem(index=0, verification_score=9, is_verified=True),
    ]
    svc = VerificationService(FakeAdapter(items))
    candidates = [_candidate(title="No sources", source_1=None, source_2=None)]
    result = svc.verify_batch(channel_topic="t", candidates=candidates, min_sources=2)
    assert result[0].is_verified is False
    assert result[0].verification_score <= 4


def test_verify_batch_one_source_below_min():
    items = [
        VerificationItem(index=0, verification_score=7, is_verified=True),
    ]
    svc = VerificationService(FakeAdapter(items))
    candidates = [_candidate(title="One src", source_1="A", source_2=None)]
    result = svc.verify_batch(channel_topic="t", candidates=candidates, min_sources=2)
    assert result[0].is_verified is False


def test_verify_batch_missing_index(caplog):
    items = [
        VerificationItem(index=0, verification_score=8, is_verified=True),
        # index=1 missing!
    ]
    svc = VerificationService(FakeAdapter(items))
    candidates = [_candidate(title="A"), _candidate(title="B")]
    with caplog.at_level(logging.WARNING):
        result = svc.verify_batch(channel_topic="t", candidates=candidates, min_sources=2)
    assert result[1].verification_score == 0
    assert result[1].is_verified is False
    assert "Missing verification result" in caplog.text


def test_verify_batch_whitespace_source_not_counted():
    items = [
        VerificationItem(index=0, verification_score=8, is_verified=True),
    ]
    svc = VerificationService(FakeAdapter(items))
    candidates = [_candidate(title="X", source_1="Real", source_2="   ", source_3="")]
    result = svc.verify_batch(channel_topic="t", candidates=candidates, min_sources=2)
    assert result[0].is_verified is False  # only 1 real source
