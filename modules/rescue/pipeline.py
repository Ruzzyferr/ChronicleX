"""Rescue modu pipeline orkestrasyonu: indir → başlık üret → edit → overlay → thumbnail."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.settings import Settings
from modules.rescue.downloader import download_video
from modules.rescue.editor import add_text_overlay, crop_and_trim, generate_thumbnail
from modules.rescue.title_generator import generate_dramatic_title

logger = logging.getLogger(__name__)


def run_rescue_pipeline(
    *,
    settings: Settings,
    url: str,
    output_base: Path,
    start_sec: float | None = None,
    end_sec: float | None = None,
) -> dict[str, Any]:
    """Rescue pipeline: YouTube → indir → edit → overlay → thumbnail.

    start_sec/end_sec: Compilation videolardan belirli bir segment seçmek için.

    Returns:
        Manifest dict with final_video, thumbnail, title etc.
    """
    # Dizinler
    source_dir = output_base / "source"
    video_dir = output_base / "video"
    thumbnails_dir = output_base / "thumbnails"
    source_dir.mkdir(parents=True, exist_ok=True)
    video_dir.mkdir(parents=True, exist_ok=True)
    thumbnails_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. Video indir ──
    logger.info("Adım 1/4: Video indiriliyor...")
    meta = download_video(url, source_dir)

    # ── 2. AI ile dramatik başlık üret ──
    logger.info("Adım 2/4: Dramatik başlık üretiliyor...")
    api_key = (settings.openai_api_key or "").strip()
    if not api_key:
        # Fallback: video başlığını kullan
        dramatic_title = meta.title.upper()[:50] + "!"
        logger.warning("OPENAI_API_KEY yok; video başlığı kullanıldı: %s", dramatic_title)
    else:
        dramatic_title = generate_dramatic_title(
            video_title=meta.title,
            video_description=meta.description,
            api_key=api_key,
            model=settings.openai_model,
        )

    # ── 3. Video edit: 9:16 crop + trim ──
    logger.info("Adım 3/4: Video editleniyor (9:16 crop + trim)...")
    cropped_path = video_dir / "cropped.mp4"
    crop_and_trim(
        input_path=meta.video_path,
        output_path=cropped_path,
        target_duration=59.0,
        start_sec=start_sec,
        end_sec=end_sec,
        ffmpeg_bin=settings.ffmpeg_path,
        ffprobe_bin=settings.ffprobe_path,
    )

    # ── 4a. Text overlay ekle ──
    final_path = video_dir / "final.mp4"
    add_text_overlay(
        input_path=cropped_path,
        output_path=final_path,
        text=dramatic_title,
        display_duration=3.0,
        ffmpeg_bin=settings.ffmpeg_path,
    )

    # ── 4b. Thumbnail üret ──
    logger.info("Adım 4/4: Thumbnail üretiliyor...")
    thumbnail_path = thumbnails_dir / "cover.jpg"
    generate_thumbnail(
        video_path=final_path,
        output_path=thumbnail_path,
        text=dramatic_title,
        ffmpeg_bin=settings.ffmpeg_path,
        ffprobe_bin=settings.ffprobe_path,
    )

    # Ara dosyayı temizle
    try:
        cropped_path.unlink()
    except OSError:
        pass

    # Manifest
    manifest = {
        "mode": "rescue",
        "source_url": url,
        "source_title": meta.title,
        "dramatic_title": dramatic_title,
        "source_duration": meta.duration,
        "final_video": str(final_path.resolve()),
        "thumbnail": str(thumbnail_path.resolve()),
    }
    manifest_path = video_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    logger.info("Rescue pipeline tamamlandı!")
    logger.info("  Video: %s", final_path)
    logger.info("  Thumbnail: %s", thumbnail_path)
    logger.info("  Başlık: %s", dramatic_title)

    return manifest
