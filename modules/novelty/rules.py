from __future__ import annotations

import re
from dataclasses import dataclass

from modules.shared.helpers import century, hook_pattern, norm
from modules.topic_discovery.schemas import RawCandidate
from storage.models import EditorialMemoryRow


@dataclass(frozen=True)
class EditorialSnapshot:
    titles: list[str]
    countries: list[str]
    centuries: list[int]
    categories: list[str]
    people: list[str]
    hook_patterns: list[str]


def _title_tokens(title: str) -> set[str]:
    t = re.sub(r"[^\w\s]", " ", norm(title))
    return {w for w in t.split() if len(w) > 2}


def evaluate_novelty(
    candidate: RawCandidate, snap: EditorialSnapshot
) -> tuple[bool, int, str]:
    """Return (keep, novelty_score 0-10, reason)."""
    title_n = norm(candidate.title)
    if not title_n:
        return False, 0, "empty_title"

    for prev in snap.titles:
        if title_n == norm(prev):
            return False, 0, "duplicate_title"

    hp = hook_pattern(candidate.title)
    for p in snap.hook_patterns:
        if hp and p and (hp == p or hp.startswith(p[:20])):
            return False, 0, "hook_pattern_collision"

    country_n = norm(candidate.country or "")
    if snap.countries and country_n and country_n == norm(snap.countries[-1]):
        return False, 0, "same_country_as_last"

    cat_n = norm(candidate.category or "")
    if cat_n:
        recent_cats = [norm(c) for c in snap.categories[-10:]]
        if recent_cats.count(cat_n) >= 3:
            return False, 0, "category_overuse"

    people_tokens: list[str] = []
    if candidate.people_involved:
        people_tokens = [
            norm(p) for p in re.split(r"[,;/]", candidate.people_involved) if norm(p)
        ]
    for person in people_tokens:
        hits = sum(1 for rp in snap.people if rp == person or person in rp)
        if hits >= 2:
            return False, 0, "person_overuse"

    cent = century(candidate.event_year)
    if cent is not None and snap.centuries:
        last_three = snap.centuries[-3:]
        if last_three.count(cent) >= 2:
            return True, 6, "century_cluster_soft"

    if snap.titles:
        last_tokens = _title_tokens(snap.titles[-1])
        cur_tokens = _title_tokens(candidate.title)
        if last_tokens and cur_tokens:
            overlap = len(last_tokens & cur_tokens) / max(len(cur_tokens), 1)
            if overlap > 0.55:
                return True, 7, "title_word_overlap_soft"

    return True, 9, "ok"


def snapshot_from_row(row: EditorialMemoryRow) -> EditorialSnapshot:
    """Build snapshot from EditorialMemoryRow."""
    return EditorialSnapshot(
        titles=[str(x) for x in (row.recent_titles_json or [])],
        countries=[str(x) for x in (row.recent_countries_json or [])],
        centuries=[int(x) for x in (row.recent_centuries_json or []) if x is not None],
        categories=[str(x) for x in (row.recent_categories_json or [])],
        people=[str(x).lower() for x in (row.recent_people_json or [])],
        hook_patterns=[str(x) for x in (row.recent_hook_patterns_json or [])],
    )
