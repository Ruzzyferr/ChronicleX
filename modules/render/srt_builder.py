from __future__ import annotations

import logging
import re
from pathlib import Path

from core.media_models import Scene

logger = logging.getLogger(__name__)


def _fmt_ts(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    whole = int(s)
    ms = int(round((s - whole) * 1000))
    if ms >= 1000:
        whole += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{whole:02d},{ms:03d}"


def _words(line: str) -> list[str]:
    return [w for w in re.split(r"\s+", line.strip()) if w]


def _blocks_for_scene(text: str, max_words_per_line: int = 4, max_lines: int = 2) -> list[tuple[str, str]]:
    words = _words(text)
    if not words:
        return []
    blocks: list[tuple[str, str]] = []
    per_block = max_words_per_line * max_lines
    i = 0
    while i < len(words):
        chunk = words[i : i + per_block]
        i += len(chunk)
        line1_words = chunk[:max_words_per_line]
        line2_words = chunk[max_words_per_line : max_words_per_line + max_words_per_line]
        blocks.append(
            (" ".join(line1_words), " ".join(line2_words) if line2_words else "")
        )
    return blocks


def build_srt_for_scenes(
    scenes: list[Scene],
    scene_durations: list[float],
    output_path: Path,
) -> None:
    """Split each scene's segment time evenly across its subtitle blocks."""
    if len(scenes) != len(scene_durations):
        raise ValueError("scenes and scene_durations length mismatch")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cursor = 0.0
    idx = 1
    out_lines: list[str] = []
    for scene, seg in zip(scenes, scene_durations):
        blocks = _blocks_for_scene(scene.text)
        if not blocks:
            cursor += seg
            continue
        dt = seg / len(blocks)
        for line1, line2 in blocks:
            t0, t1 = cursor, cursor + dt
            out_lines.append(str(idx))
            out_lines.append(f"{_fmt_ts(t0)} --> {_fmt_ts(t1)}")
            if line2:
                out_lines.append(line1)
                out_lines.append(line2)
            else:
                out_lines.append(line1)
            out_lines.append("")
            idx += 1
            cursor = t1
    output_path.write_text("\n".join(out_lines).rstrip() + "\n", encoding="utf-8")
    logger.info("Wrote SRT (%s cues) -> %s", idx - 1, output_path)
