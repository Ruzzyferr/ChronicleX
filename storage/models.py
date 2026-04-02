"""SQLAlchemy ORM models (PostgreSQL)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


class PortableJSON(TypeDecorator):
    """JSONB on PostgreSQL, JSON on other dialects (e.g. SQLite for tests)."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):  # type: ignore[override]
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB

            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class Base(DeclarativeBase):
    pass


class TopicRow(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_topic: Mapped[str] = mapped_column(String(512), index=True)
    title: Mapped[str] = mapped_column(String(1024))
    summary: Mapped[str] = mapped_column(Text, default="")
    event_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    country: Mapped[str | None] = mapped_column(String(256), nullable=True)
    region: Mapped[str | None] = mapped_column(String(256), nullable=True)
    category: Mapped[str | None] = mapped_column(String(256), nullable=True)
    subcategory: Mapped[str | None] = mapped_column(String(256), nullable=True)
    people_involved: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    source_1: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_2: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_3: Mapped[str | None] = mapped_column(Text, nullable=True)
    shock_score: Mapped[int] = mapped_column(Integer, default=0)
    fear_score: Mapped[int] = mapped_column(Integer, default=0)
    clarity_score: Mapped[int] = mapped_column(Integer, default=0)
    visual_score: Mapped[int] = mapped_column(Integer, default=0)
    novelty_score: Mapped[int] = mapped_column(Integer, default=0)
    verification_score: Mapped[int] = mapped_column(Integer, default=0)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    ready_for_script: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    published_videos: Mapped[list["PublishedVideoRow"]] = relationship(
        back_populates="topic",
    )


class PublishedVideoRow(Base):
    __tablename__ = "published_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("topics.id", ondelete="SET NULL"), nullable=True
    )
    channel_topic: Mapped[str] = mapped_column(String(512), index=True)
    script_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    youtube_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tiktok_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    instagram_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    youtube_video_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tiktok_publish_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    instagram_media_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    publish_queue_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    topic: Mapped["TopicRow | None"] = relationship(back_populates="published_videos")


class EditorialMemoryRow(Base):
    __tablename__ = "editorial_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_topic: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    recent_titles_json: Mapped[list[Any]] = mapped_column(
        PortableJSON, nullable=False, default=list
    )
    recent_countries_json: Mapped[list[Any]] = mapped_column(
        PortableJSON, nullable=False, default=list
    )
    recent_centuries_json: Mapped[list[Any]] = mapped_column(
        PortableJSON, nullable=False, default=list
    )
    recent_categories_json: Mapped[list[Any]] = mapped_column(
        PortableJSON, nullable=False, default=list
    )
    recent_people_json: Mapped[list[Any]] = mapped_column(
        PortableJSON, nullable=False, default=list
    )
    recent_hook_patterns_json: Mapped[list[Any]] = mapped_column(
        PortableJSON, nullable=False, default=list
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class JobRunRow(Base):
    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32))
    details_json: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON, nullable=False, default=dict
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
