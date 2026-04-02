from modules.novelty.rules import EditorialSnapshot, evaluate_novelty
from modules.topic_discovery.schemas import RawCandidate


def test_rejects_duplicate_title() -> None:
    c = RawCandidate(title="Unique Event", summary="x", event_year=1900, country="FR")
    snap = EditorialSnapshot(
        titles=["Unique Event"],
        countries=[],
        centuries=[],
        categories=[],
        people=[],
        hook_patterns=[],
    )
    ok, score, reason = evaluate_novelty(c, snap)
    assert not ok and score == 0 and reason == "duplicate_title"


def test_rejects_same_country_as_last() -> None:
    c = RawCandidate(title="Another", summary="x", country="DE")
    snap = EditorialSnapshot(
        titles=["Old"],
        countries=["DE"],
        centuries=[],
        categories=[],
        people=[],
        hook_patterns=[],
    )
    ok, _, reason = evaluate_novelty(c, snap)
    assert not ok and reason == "same_country_as_last"


def test_accepts_fresh_candidate() -> None:
    c = RawCandidate(
        title="Forgotten battle in the Balkans",
        summary="Real event",
        event_year=1878,
        country="RS",
        category="war",
    )
    snap = EditorialSnapshot(
        titles=["Different title"],
        countries=["FR"],
        centuries=[19],
        categories=["politics"],
        people=[],
        hook_patterns=[],
    )
    ok, score, reason = evaluate_novelty(c, snap)
    assert ok and score >= 6 and reason in ("ok", "century_cluster_soft", "title_word_overlap_soft")
