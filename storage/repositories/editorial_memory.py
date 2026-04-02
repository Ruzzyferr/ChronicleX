from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from storage.models import EditorialMemoryRow


def get_or_create(session: Session, channel_topic: str) -> EditorialMemoryRow:
    stmt = select(EditorialMemoryRow).where(
        EditorialMemoryRow.channel_topic == channel_topic
    )
    row = session.scalars(stmt).first()
    if row is not None:
        return row
    row = EditorialMemoryRow(channel_topic=channel_topic)
    session.add(row)
    session.flush()
    return row


def _append_cap(lst: list[Any], value: Any, cap: int) -> list[Any]:
    if value is None or value == "":
        return lst
    out = list(lst)
    out.append(value)
    return out[-cap:]


def update_after_selection(
    session: Session,
    channel_topic: str,
    *,
    title: str,
    country: str | None,
    century: int | None,
    category: str | None,
    people: str | None,
    hook_pattern: str,
    cap: int = 24,
) -> None:
    row = get_or_create(session, channel_topic)
    row.recent_titles_json = _append_cap(list(row.recent_titles_json or []), title, cap)
    row.recent_countries_json = _append_cap(
        list(row.recent_countries_json or []), country, cap
    )
    if century is not None:
        row.recent_centuries_json = _append_cap(
            list(row.recent_centuries_json or []), century, cap
        )
    row.recent_categories_json = _append_cap(
        list(row.recent_categories_json or []), category, cap
    )
    if people:
        for p in [x.strip() for x in people.split(",") if x.strip()]:
            row.recent_people_json = _append_cap(
                list(row.recent_people_json or []), p.lower(), cap * 2
            )
    row.recent_hook_patterns_json = _append_cap(
        list(row.recent_hook_patterns_json or []), hook_pattern.lower(), cap
    )
    session.add(row)
