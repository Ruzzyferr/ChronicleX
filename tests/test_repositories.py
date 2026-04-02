"""Tests for storage repositories — topics, editorial_memory, job_runs."""

from __future__ import annotations

from storage.models import EditorialMemoryRow, TopicRow
from storage.repositories import editorial_memory as em_repo
from storage.repositories import job_runs as job_repo
from storage.repositories import topics as topics_repo


# --- topics ---


def test_insert_topic_returns_row_with_id(db_session):
    row = TopicRow(channel_topic="ch", title="Test Title", summary="s")
    result = topics_repo.insert_topic(db_session, row)
    assert result.id is not None
    assert result.id > 0


def test_set_ready_for_script_clears_previous(db_session):
    r1 = TopicRow(channel_topic="ch", title="First", summary="s", ready_for_script=True)
    r2 = TopicRow(channel_topic="ch", title="Second", summary="s")
    topics_repo.insert_topic(db_session, r1)
    topics_repo.insert_topic(db_session, r2)
    db_session.flush()

    topics_repo.set_ready_for_script(db_session, r2.id, "ch")
    db_session.flush()

    db_session.refresh(r1)
    db_session.refresh(r2)
    assert r1.ready_for_script is False
    assert r2.ready_for_script is True


def test_list_recent_topics_ordering_and_limit(db_session):
    for i in range(5):
        topics_repo.insert_topic(
            db_session,
            TopicRow(channel_topic="ch", title=f"Topic {i}", summary="s"),
        )
    db_session.flush()

    results = topics_repo.list_recent_topics(db_session, "ch", limit=3)
    assert len(results) == 3


def test_get_ready_topic(db_session):
    r1 = TopicRow(channel_topic="ch", title="Not ready", summary="s")
    r2 = TopicRow(channel_topic="ch", title="Ready", summary="s")
    topics_repo.insert_topic(db_session, r1)
    topics_repo.insert_topic(db_session, r2)
    topics_repo.set_ready_for_script(db_session, r2.id, "ch")
    db_session.flush()

    ready = topics_repo.get_ready_topic(db_session, "ch")
    assert ready is not None
    assert ready.title == "Ready"


def test_get_ready_topic_none(db_session):
    topics_repo.insert_topic(
        db_session,
        TopicRow(channel_topic="ch", title="Not ready", summary="s"),
    )
    db_session.flush()

    assert topics_repo.get_ready_topic(db_session, "ch") is None


def test_title_exists(db_session):
    topics_repo.insert_topic(
        db_session,
        TopicRow(channel_topic="ch", title="Some Title", summary="s"),
    )
    db_session.flush()

    assert topics_repo.title_exists(db_session, "ch", "Some Title") is True
    assert topics_repo.title_exists(db_session, "ch", "some title") is True
    assert topics_repo.title_exists(db_session, "ch", "Other Title") is False


# --- editorial_memory ---


def test_em_get_or_create_new(db_session):
    row = em_repo.get_or_create(db_session, "new_channel")
    assert row.channel_topic == "new_channel"
    assert row.recent_titles_json == []


def test_em_get_or_create_existing(db_session):
    row1 = em_repo.get_or_create(db_session, "ch")
    db_session.flush()
    row2 = em_repo.get_or_create(db_session, "ch")
    assert row1.id == row2.id


def test_em_update_after_selection(db_session):
    em_repo.get_or_create(db_session, "ch")
    db_session.flush()

    em_repo.update_after_selection(
        db_session, "ch",
        title="Great Event",
        country="TR",
        century=19,
        category="war",
        people="Napoleon, Wellington",
        hook_pattern="great event",
    )
    db_session.flush()

    row = em_repo.get_or_create(db_session, "ch")
    assert "Great Event" in row.recent_titles_json
    assert "TR" in row.recent_countries_json
    assert 19 in row.recent_centuries_json
    assert "war" in row.recent_categories_json
    assert "napoleon" in row.recent_people_json
    assert "wellington" in row.recent_people_json


def test_em_append_cap(db_session):
    em_repo.get_or_create(db_session, "ch")
    db_session.flush()

    for i in range(30):
        em_repo.update_after_selection(
            db_session, "ch",
            title=f"Title {i}",
            country=f"C{i}",
            century=None,
            category=f"cat{i}",
            people=None,
            hook_pattern=f"hook{i}",
            cap=5,
        )
    db_session.flush()

    row = em_repo.get_or_create(db_session, "ch")
    assert len(row.recent_titles_json) == 5
    assert len(row.recent_countries_json) == 5


# --- job_runs ---


def test_job_start_complete_cycle(db_session):
    job = job_repo.start_job(db_session, "discovery", {"key": "val"})
    assert job.status == "running"
    assert job.id is not None

    job_repo.complete_job(db_session, job.id, {"result": "ok"})
    db_session.flush()
    db_session.refresh(job)
    assert job.status == "success"
    assert job.details_json["result"] == "ok"
    assert job.details_json["key"] == "val"


def test_job_fail_records_error(db_session):
    job = job_repo.start_job(db_session, "discovery", {})
    job_repo.fail_job(db_session, job.id, "Something went wrong")
    db_session.flush()
    db_session.refresh(job)
    assert job.status == "failed"
    assert job.error_message == "Something went wrong"
