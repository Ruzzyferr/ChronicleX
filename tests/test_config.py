"""Tests for config loading and settings."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from app.config_loader import load_topic_config
from app.settings import Settings


def test_load_topic_config_valid():
    yaml_content = """
topic_name: "Test Topic"
language: "en"
tone: "neutral"
video_duration_seconds: 30
content_rules:
  must_be_real: true
  min_sources: 1
publishing:
  youtube_enabled: false
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        tc = load_topic_config(Path(f.name))
    os.unlink(f.name)

    assert tc.topic_name == "Test Topic"
    assert tc.language == "en"
    assert tc.content_rules.min_sources == 1
    assert tc.publishing.youtube_enabled is False


def test_load_topic_config_missing_file():
    from core.exceptions import ConfigError

    with pytest.raises(ConfigError):
        load_topic_config(Path("/nonexistent/path/topic.yaml"))


def test_load_topic_config_override_topic_name():
    yaml_content = """
topic_name: "Original"
language: "tr"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        tc = load_topic_config(Path(f.name), topic_override="Overridden")
    os.unlink(f.name)

    assert tc.topic_name == "Overridden"


def test_settings_defaults():
    s = Settings(
        _env_file=None,
        database_url="postgresql://x:x@localhost/db",
    )
    assert s.default_language == "tr"
    assert s.default_timezone == "Europe/Istanbul"
    assert s.dry_run is False
    assert s.openai_model == "gpt-4o-mini"


def test_settings_empty_output_dir():
    s = Settings(
        _env_file=None,
        database_url="postgresql://x:x@localhost/db",
        output_dir="",
    )
    assert s.output_dir is None
