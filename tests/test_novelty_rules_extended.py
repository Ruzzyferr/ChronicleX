"""Extended tests for novelty rules — each rule independently + edge cases."""

from __future__ import annotations

from modules.novelty.rules import EditorialSnapshot, evaluate_novelty, snapshot_from_row
from modules.topic_discovery.schemas import RawCandidate
from storage.models import EditorialMemoryRow


def _snap(**overrides) -> EditorialSnapshot:
    defaults = dict(
        titles=[], countries=[], centuries=[],
        categories=[], people=[], hook_patterns=[],
    )
    defaults.update(overrides)
    return EditorialSnapshot(**defaults)


def test_empty_title_rejected():
    c = RawCandidate(title="", summary="x")
    ok, score, reason = evaluate_novelty(c, _snap())
    assert not ok and score == 0 and reason == "empty_title"


def test_whitespace_only_title_rejected():
    c = RawCandidate(title="   ", summary="x")
    ok, score, reason = evaluate_novelty(c, _snap())
    assert not ok and score == 0 and reason == "empty_title"


def test_duplicate_title_case_insensitive():
    c = RawCandidate(title="Great Fire of London", summary="x")
    snap = _snap(titles=["great fire of london"])
    ok, _, reason = evaluate_novelty(c, snap)
    assert not ok and reason == "duplicate_title"


def test_hook_pattern_collision_exact():
    c = RawCandidate(title="The mysterious death of a forgotten king in medieval europe", summary="x")
    snap = _snap(hook_patterns=["the mysterious death of a forgotten kin"])
    ok, _, reason = evaluate_novelty(c, snap)
    assert not ok and reason == "hook_pattern_collision"


def test_hook_pattern_collision_prefix():
    c = RawCandidate(title="The lost city under the sea discovered by divers", summary="x")
    stored = "the lost city under "  # 20 chars
    snap = _snap(hook_patterns=[stored])
    ok, _, reason = evaluate_novelty(c, snap)
    assert not ok and reason == "hook_pattern_collision"


def test_hook_pattern_no_collision_different():
    c = RawCandidate(title="Something completely different and unique", summary="x")
    snap = _snap(hook_patterns=["the ancient ruins of"])
    ok, _, reason = evaluate_novelty(c, snap)
    assert ok


def test_category_overuse_at_threshold():
    c = RawCandidate(title="New War Event", summary="x", category="war")
    snap = _snap(categories=["war", "politics", "war", "science", "war", "art"])
    ok, _, reason = evaluate_novelty(c, snap)
    assert not ok and reason == "category_overuse"


def test_category_overuse_below_threshold():
    c = RawCandidate(title="New War Event", summary="x", category="war")
    snap = _snap(categories=["war", "politics", "war", "science", "art"])
    ok, _, _ = evaluate_novelty(c, snap)
    assert ok


def test_person_overuse():
    c = RawCandidate(title="Napoleon's Secret", summary="x", people_involved="Napoleon")
    snap = _snap(people=["napoleon", "napoleon"])
    ok, _, reason = evaluate_novelty(c, snap)
    assert not ok and reason == "person_overuse"


def test_person_single_mention_ok():
    c = RawCandidate(title="Napoleon's Secret", summary="x", people_involved="Napoleon")
    snap = _snap(people=["napoleon"])
    ok, _, _ = evaluate_novelty(c, snap)
    assert ok


def test_century_cluster_soft_penalty():
    c = RawCandidate(title="Event in 1850", summary="x", event_year=1850, country="UK")
    snap = _snap(centuries=[19, 19], countries=["FR"])
    ok, score, reason = evaluate_novelty(c, snap)
    assert ok and score == 6 and reason == "century_cluster_soft"


def test_century_cluster_one_is_fine():
    c = RawCandidate(title="Event in 1850", summary="x", event_year=1850, country="UK")
    snap = _snap(centuries=[19, 18, 20], countries=["FR"])
    ok, score, _ = evaluate_novelty(c, snap)
    assert ok and score == 9


def test_title_word_overlap_soft():
    c = RawCandidate(title="The great mysterious battle of forgotten empires", summary="x")
    snap = _snap(titles=["The great mysterious battle of ancient empires"])
    ok, score, reason = evaluate_novelty(c, snap)
    assert ok and score == 7 and reason == "title_word_overlap_soft"


def test_title_word_overlap_below_threshold():
    c = RawCandidate(title="Completely different topic about science", summary="x")
    snap = _snap(titles=["The great mysterious battle of ancient empires"])
    ok, score, _ = evaluate_novelty(c, snap)
    assert ok and score == 9


def test_snapshot_from_row_with_none_values():
    row = EditorialMemoryRow(
        channel_topic="test",
        recent_titles_json=["a", None, "b"],
        recent_countries_json=[],
        recent_centuries_json=[19, None, 20],
        recent_categories_json=[],
        recent_people_json=[],
        recent_hook_patterns_json=[],
    )
    snap = snapshot_from_row(row)
    assert snap.titles == ["a", "None", "b"]
    assert snap.centuries == [19, 20]  # None filtered out


def test_snapshot_from_row_empty():
    row = EditorialMemoryRow(channel_topic="test")
    snap = snapshot_from_row(row)
    assert snap.titles == []
    assert snap.countries == []
    assert snap.centuries == []


def test_fresh_candidate_passes():
    c = RawCandidate(
        title="Unique historical event never seen before",
        summary="Real event",
        event_year=1700,
        country="JP",
        category="culture",
    )
    snap = _snap(
        titles=["Other title"],
        countries=["FR"],
        centuries=[18],
        categories=["war"],
    )
    ok, score, reason = evaluate_novelty(c, snap)
    assert ok and score >= 6
