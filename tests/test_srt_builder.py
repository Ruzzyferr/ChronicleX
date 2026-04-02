from pathlib import Path

from core.media_models import Scene
from modules.render.media_pipeline import allocate_scene_times
from modules.render.srt_builder import _fmt_ts, build_srt_for_scenes


def test_fmt_ts_zero():
    assert _fmt_ts(0) == "00:00:00,000"


def test_fmt_ts_with_ms():
    assert _fmt_ts(61.5) == "00:01:01,500"


def test_allocate_scene_times():
    scenes = [
        Scene(scene_id=1, duration=4, text="a", image_prompt="p", motion="zoom_in"),
        Scene(scene_id=2, duration=6, text="b", image_prompt="p", motion="zoom_in"),
    ]
    t = allocate_scene_times(scenes, 30.0)
    assert abs(sum(t) - 30.0) < 1e-6
    assert abs(t[0] - 12.0) < 1e-6
    assert abs(t[1] - 18.0) < 1e-6


def test_build_srt_creates_file(tmp_path: Path):
    scenes = [
        Scene(
            scene_id=1,
            duration=4,
            text="one two three four five",
            image_prompt="x",
            motion="zoom_in",
        ),
    ]
    out = tmp_path / "sub.srt"
    build_srt_for_scenes(scenes, [2.0], out)
    body = out.read_text(encoding="utf-8")
    assert "one two three four" in body or "one two" in body
    assert "-->" in body
