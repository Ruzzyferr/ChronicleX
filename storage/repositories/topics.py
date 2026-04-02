from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from storage.models import TopicRow


def clear_ready_for_script(session: Session, channel_topic: str) -> None:
    session.execute(
        update(TopicRow)
        .where(TopicRow.channel_topic == channel_topic)
        .values(ready_for_script=False)
    )


def insert_topic(session: Session, row: TopicRow) -> TopicRow:
    session.add(row)
    session.flush()
    return row


def set_ready_for_script(session: Session, topic_id: int, channel_topic: str) -> None:
    clear_ready_for_script(session, channel_topic)
    session.execute(
        update(TopicRow)
        .where(TopicRow.id == topic_id)
        .values(ready_for_script=True)
    )


def get_ready_topic(session: Session, channel_topic: str) -> TopicRow | None:
    stmt = (
        select(TopicRow)
        .where(TopicRow.channel_topic == channel_topic)
        .where(TopicRow.ready_for_script == True)  # noqa: E712
        .order_by(TopicRow.updated_at.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def title_exists(session: Session, channel_topic: str, title: str) -> bool:
    stmt = (
        select(TopicRow.id)
        .where(TopicRow.channel_topic == channel_topic)
        .where(func.lower(TopicRow.title) == title.strip().lower())
        .limit(1)
    )
    return session.scalars(stmt).first() is not None


def list_recent_topics(
    session: Session, channel_topic: str, limit: int = 30
) -> list[TopicRow]:
    stmt = (
        select(TopicRow)
        .where(TopicRow.channel_topic == channel_topic)
        .order_by(TopicRow.created_at.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt).all())
