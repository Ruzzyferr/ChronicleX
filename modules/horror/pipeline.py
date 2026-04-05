"""Korku filmi trailer pipeline: film seç → trailer indir → 9:16 edit → hook overlay → thumbnail."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.settings import Settings
from modules.horror.movie_suggest import interactive_movie_select
from modules.rescue.editor import (
    add_text_overlay,
    crop_and_trim,
    generate_thumbnail,
)
from modules.visuals.trailer_dl import search_and_download_trailer

logger = logging.getLogger(__name__)


def run_horror_pipeline(
    *,
    settings: Settings,
    output_base: Path,
    movie_title: str | None = None,
    hook_text: str | None = None,
) -> dict[str, Any]:
    """Korku filmi trailer pipeline.

    movie_title/hook_text verilmezse interaktif seçim yapılır.

    Returns:
        Manifest dict with final_video, thumbnail, title etc.
    """
    api_key = (settings.openai_api_key or "").strip()

    # Dizinler
    trailer_dir = output_base / "trailer"
    video_dir = output_base / "video"
    thumbnails_dir = output_base / "thumbnails"
    for d in (trailer_dir, video_dir, thumbnails_dir):
        d.mkdir(parents=True, exist_ok=True)

    # ── 1. Film seçimi ──
    if not movie_title:
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY gerekli (film önerisi için).")
        logger.info("Adım 1/4: Film seçimi...")
        movie_title, hook_text = interactive_movie_select(
            api_key=api_key, model=settings.openai_model,
        )
    if not hook_text:
        hook_text = "Bu filmi sinemada izlemeye cesaret edebilir misin?"

    logger.info("Film: %s", movie_title)
    logger.info("Hook: %s", hook_text)

    # ── 2. Trailer indir ──
    logger.info("Adım 2/4: Trailer indiriliyor...")
    trailer_path = search_and_download_trailer(
        topic=f"{movie_title} official trailer",
        output_dir=trailer_dir,
        max_duration=300,
    )
    if trailer_path is None:
        raise RuntimeError(
            f"Trailer indirilemedi: '{movie_title}'. "
            "yt-dlp yüklü mü? Film adı doğru mu?"
        )

    # ── 3. Video edit: 9:16 crop ──
    logger.info("Adım 3/4: Trailer editleniyor (9:16 crop)...")
    cropped_path = video_dir / "cropped.mp4"
    crop_and_trim(
        input_path=trailer_path,
        output_path=cropped_path,
        target_duration=59.0,
        ffmpeg_bin=settings.ffmpeg_path,
        ffprobe_bin=settings.ffprobe_path,
    )

    # ── 4a. Hook text overlay ──
    final_path = video_dir / "final.mp4"
    add_text_overlay(
        input_path=cropped_path,
        output_path=final_path,
        text=hook_text,
        display_duration=3.5,
        ffmpeg_bin=settings.ffmpeg_path,
    )

    # ── 4b. Thumbnail ──
    logger.info("Adım 4/4: Thumbnail üretiliyor...")
    thumbnail_path = thumbnails_dir / "cover.jpg"
    generate_thumbnail(
        video_path=final_path,
        output_path=thumbnail_path,
        text=movie_title.upper(),
        ffmpeg_bin=settings.ffmpeg_path,
        ffprobe_bin=settings.ffprobe_path,
    )

    # Temizle
    try:
        cropped_path.unlink()
    except OSError:
        pass

    # Manifest
    manifest = {
        "mode": "horror",
        "movie_title": movie_title,
        "hook_text": hook_text,
        "final_video": str(final_path.resolve()),
        "thumbnail": str(thumbnail_path.resolve()),
    }
    manifest_path = video_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    logger.info("Horror trailer pipeline tamamlandı!")
    logger.info("  Video: %s", final_path)
    logger.info("  Thumbnail: %s", thumbnail_path)
    logger.info("  Film: %s", movie_title)
    logger.info("  Hook: %s", hook_text)

    return manifest
