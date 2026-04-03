from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.exceptions import ConfigError
from core.production_paths import (
    find_latest_final_video,
    production_run_dir,
    read_last_run_dir,
    resolve_video_for_publish,
    slugify_topic,
)


def test_slugify_topic_turkish() -> None:
    assert "turk" in slugify_topic("Türk tarihi ★ olay")
    assert slugify_topic("!!!") == "topic"


def test_production_run_dir_shape(tmp_path: Path) -> None:
    when = datetime(2026, 4, 2, 12, 30, 0, tzinfo=timezone.utc)
    d = production_run_dir(tmp_path, "Test Başlık", when=when)
    assert d.parent.name == "productions"
    assert d.name.startswith("2026-04-02_123000__")
    assert "test" in d.name


def test_find_latest_prefers_newest(tmp_path: Path) -> None:
    prod = tmp_path / "productions"
    old = prod / "2026-01-01__a" / "video"
    new = prod / "2026-02-01__b" / "video"
    old.mkdir(parents=True)
    new.mkdir(parents=True)
    (old / "final.mp4").write_bytes(b"a")
    (new / "final.mp4").write_bytes(b"b")
    old_stat = (old / "final.mp4").stat()
    new_path = new / "final.mp4"
    os.utime(new_path, (old_stat.st_mtime + 10, old_stat.st_mtime + 10))
    assert find_latest_final_video(tmp_path) == new_path


def test_resolve_video_for_publish_missing(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        resolve_video_for_publish(tmp_path)


def test_read_last_run_dir(tmp_path: Path) -> None:
    assert read_last_run_dir(tmp_path) is None
    run_dir = tmp_path / "productions" / "2026-01-01__x"
    run_dir.mkdir(parents=True)
    ptr = tmp_path / "productions" / "_last_run.txt"
    ptr.write_text(str(run_dir.resolve()) + "\n", encoding="utf-8")
    assert read_last_run_dir(tmp_path) == run_dir.resolve()
