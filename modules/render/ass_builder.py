"""TikTok / Reels tarzı stilize ASS (Advanced SubStation Alpha) altyazı üretici."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from core.media_models import Scene
from modules.render.srt_builder import _blocks_for_scene

logger = logging.getLogger(__name__)

_STYLES_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "styles.yaml"

# Varsayılan stil değerleri (styles.yaml yoksa veya eksik alan varsa)
_DEFAULTS = {
    "font_name": "Arial Bold",
    "font_size": 52,
    "primary_color": "&H00FFFFFF",
    "outline_color": "&H00000000",
    "outline_width": 4,
    "shadow_depth": 2,
    "alignment": 5,
}


def _load_caption_style() -> dict:
    """styles.yaml'dan caption stilini yükle, eksik alanları default ile doldur."""
    style = dict(_DEFAULTS)
    try:
        raw = yaml.safe_load(_STYLES_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and "captions" in raw:
            for k, v in raw["captions"].items():
                if k in _DEFAULTS:
                    style[k] = v
    except Exception:
        logger.warning("styles.yaml okunamadı, varsayılan caption stili kullanılıyor.")
    return style


def _fmt_ass_ts(seconds: float) -> str:
    """ASS zaman formatı: H:MM:SS.cc (santiiye)."""
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    whole = int(s)
    cs = int(round((s - whole) * 100))
    if cs >= 100:
        whole += 1
        cs = 0
    return f"{h}:{m:02d}:{whole:02d}.{cs:02d}"


def _ass_header(style: dict) -> str:
    """ASS dosya başlığı ve stil tanımı."""
    font = style["font_name"]
    size = style["font_size"]
    primary = style["primary_color"]
    outline = style["outline_color"]
    outline_w = style["outline_width"]
    shadow = style["shadow_depth"]
    align = style["alignment"]

    return (
        "[Script Info]\n"
        "Title: ChronicleX Subtitles\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font},{size},{primary},&H000000FF,"
        f"{outline},&H80000000,-1,0,0,0,100,100,0,0,1,"
        f"{outline_w},{shadow},{align},40,40,100,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


def build_ass_for_scenes(
    scenes: list[Scene],
    scene_durations: list[float],
    output_path: Path,
) -> None:
    """Sahne listesinden stilize ASS altyazı dosyası üretir."""
    if len(scenes) != len(scene_durations):
        raise ValueError("scenes and scene_durations length mismatch")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    style = _load_caption_style()

    lines: list[str] = [_ass_header(style)]
    cursor = 0.0

    for scene, seg in zip(scenes, scene_durations):
        blocks = _blocks_for_scene(scene.text)
        if not blocks:
            cursor += seg
            continue
        dt = seg / len(blocks)
        for line1, line2 in blocks:
            t0 = _fmt_ass_ts(cursor)
            t1 = _fmt_ass_ts(cursor + dt)
            text = line1
            if line2:
                text = f"{line1}\\N{line2}"
            lines.append(
                f"Dialogue: 0,{t0},{t1},Default,,0,0,0,,{text}"
            )
            cursor += dt

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote ASS (%s dialogue lines) -> %s", len(lines) - 1, output_path)


def build_ass_from_whisper(words: list[dict], output_path: Path) -> None:
    """Word timestamp list -> ASS subtitles (4+4 block style)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    style = _load_caption_style()
    lines: list[str] = [_ass_header(style)]

    if not words:
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.warning("Whisper words empty, wrote ASS header only: %s", output_path)
        return

    chunk_size = 8
    for i in range(0, len(words), chunk_size):
        chunk = words[i : i + chunk_size]
        if not chunk:
            continue
        first = chunk[0]
        last = chunk[-1]
        try:
            start = float(first["start"])
            end = float(last["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if end <= start:
            end = start + 0.2

        first_line_words = [str(w.get("word", "")).strip() for w in chunk[:4]]
        second_line_words = [str(w.get("word", "")).strip() for w in chunk[4:8]]
        line1 = " ".join(w for w in first_line_words if w)
        line2 = " ".join(w for w in second_line_words if w)
        if not line1 and not line2:
            continue
        text = line1 if not line2 else f"{line1}\\N{line2}"
        lines.append(
            f"Dialogue: 0,{_fmt_ass_ts(start)},{_fmt_ass_ts(end)},Default,,0,0,0,,{text}"
        )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote Whisper ASS (%s dialogue lines) -> %s", len(lines) - 1, output_path)
