"""Shared utility functions used across discovery, novelty, and verification modules."""

from __future__ import annotations

import re

from modules.topic_discovery.schemas import RawCandidate


def norm(s: str | None) -> str:
    """Normalize a string: strip, lowercase, collapse whitespace."""
    if not s:
        return ""
    return re.sub(r"\s+", " ", s.strip().lower())


def source_count(c: RawCandidate) -> int:
    """Count non-empty sources on a candidate."""
    n = 0
    for s in (c.source_1, c.source_2, c.source_3):
        if s and str(s).strip():
            n += 1
    return n


def century(year: int | None) -> int | None:
    """Return century number for a year, or None."""
    if year is None or year <= 0:
        return None
    return (year - 1) // 100 + 1


def hook_pattern(title: str) -> str:
    """Return normalized, truncated hook pattern for novelty comparison."""
    t = norm(title)
    return t[:40] if t else ""
