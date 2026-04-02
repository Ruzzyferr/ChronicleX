"""Publish coordinator — dry-run üç platform, credential yok."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.settings import Settings
from core.exceptions import ConfigError
from core.models import PublishingFlags, TopicConfig
from modules.publishers.coordinator import publish_to_all_enabled_platforms


def test_publish_dry_run_three_platforms_no_file():
    s = Settings(_env_file=None, database_url="postgresql://u:p@localhost/db")
    topic = TopicConfig(topic_name="Tek başlık üç platform")
    results = publish_to_all_enabled_platforms(
        s, topic, Path("output/video/final.mp4"), dry_run=True
    )
    assert len(results) == 3
    assert all(r.success for r in results)
    assert all(r.dry_run for r in results)
    platforms = {r.platform for r in results}
    assert platforms == {"youtube", "tiktok", "instagram"}


def test_publish_no_platform_enabled():
    s = Settings(_env_file=None, database_url="postgresql://u:p@localhost/db")
    topic = TopicConfig(
        topic_name="x",
        publishing=PublishingFlags(
            youtube_enabled=False,
            tiktok_enabled=False,
            instagram_enabled=False,
        ),
    )
    with pytest.raises(ConfigError):
        publish_to_all_enabled_platforms(
            s, topic, Path("output/video/final.mp4"), dry_run=True
        )
