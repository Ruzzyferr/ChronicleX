"""Shared test fixtures for ChronicleX."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from modules.novelty.rules import EditorialSnapshot
from modules.topic_discovery.schemas import RawCandidate
from storage.models import Base


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session  # type: ignore[misc]
    session.close()
    engine.dispose()


@pytest.fixture()
def make_candidate():
    def _make(**overrides) -> RawCandidate:
        defaults = dict(
            title="Test Event Title",
            summary="A real historical event",
            event_year=1900,
            country="TR",
            region="Anatolia",
            category="war",
            subcategory="battle",
            people_involved="Person A, Person B",
            source_1="Encyclopedia Britannica",
            source_2="National Archives",
            source_3=None,
            shock_score=7,
            fear_score=5,
            clarity_score=7,
            visual_score=7,
        )
        defaults.update(overrides)
        return RawCandidate(**defaults)

    return _make


@pytest.fixture()
def empty_snapshot() -> EditorialSnapshot:
    return EditorialSnapshot(
        titles=[],
        countries=[],
        centuries=[],
        categories=[],
        people=[],
        hook_patterns=[],
    )
