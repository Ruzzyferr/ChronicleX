"""PostgreSQL entegrasyon testleri — Docker `docker compose up -d` sonrası çalıştırın.

Ortam:
  set CHRONICLE_INTEGRATION=1
  (opsiyonel) set CHRONICLE_TEST_DATABASE_URL=postgresql+psycopg2://...

Varsayılan URL docker-compose.yml ile uyumludur (localhost:5433).
"""

from __future__ import annotations

import os

import pytest

from storage.db import ensure_schema, reset_engine_cache, session_scope
from storage.models import TopicRow
from storage.repositories import topics as topics_repo

pytestmark = pytest.mark.integration


def _integration_enabled() -> bool:
    v = os.environ.get("CHRONICLE_INTEGRATION", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _postgres_url() -> str:
    url = os.environ.get("CHRONICLE_TEST_DATABASE_URL", "").strip()
    if url:
        return url
    return "postgresql+psycopg2://chroniclex:chroniclex@127.0.0.1:5433/chroniclex"


@pytest.fixture(scope="module")
def pg_url() -> str:
    if not _integration_enabled():
        pytest.skip(
            "PostgreSQL entegrasyonu için CHRONICLE_INTEGRATION=1 ve çalışan Docker Postgres gerekir."
        )
    return _postgres_url()


@pytest.fixture(scope="module", autouse=True)
def _postgres_schema(pg_url: str) -> None:
    reset_engine_cache()
    ensure_schema(pg_url)
    yield
    reset_engine_cache()


def test_postgres_ping_and_roundtrip(pg_url: str) -> None:
    row = TopicRow(
        channel_topic="integration-test-channel",
        title="Integration Topic",
        summary="test",
        shock_score=5,
        fear_score=5,
        clarity_score=5,
        visual_score=5,
        novelty_score=5,
        verification_score=5,
        is_verified=True,
        ready_for_script=False,
    )
    with session_scope(pg_url) as session:
        topics_repo.insert_topic(session, row)
        tid = row.id
    assert tid > 0

    with session_scope(pg_url) as session:
        loaded = session.get(TopicRow, tid)
        assert loaded is not None
        assert loaded.title == "Integration Topic"
        assert loaded.channel_topic == "integration-test-channel"


def test_editorial_memory_json_roundtrip(pg_url: str) -> None:
    from storage.repositories import editorial_memory as em_repo

    ch = "integration-em-channel"
    with session_scope(pg_url) as session:
        em_repo.update_after_selection(
            session,
            ch,
            title="T1",
            country="TR",
            century=20,
            category="war",
            people="Ali, Veli",
            hook_pattern="forgotten",
        )
    with session_scope(pg_url) as session:
        r = em_repo.get_or_create(session, ch)
        assert "T1" in (r.recent_titles_json or [])
        assert "TR" in (r.recent_countries_json or [])
