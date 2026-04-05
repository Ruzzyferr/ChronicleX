"""Rescue modu pipeline orkestrasyonu: indir → başlık+hook üret → edit → voice → overlay → thumbnail."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.settings import Settings
from modules.rescue.downloader import download_video
from modules.rescue.editor import (
    add_text_overlay,
    crop_and_trim,
    generate_thumbnail,
    mix_hook_voice,
)
from modules.rescue.title_generator import generate_title_and_hook
from modules.voice.elevenlabs import generate_voice_mp3

logger = logging.getLogger(__name__)


def run_rescue_pipeline(
    *,
    settings: Settings,
    url: str,
    output_base: Path,
    start_sec: float | None = None,
    end_sec: float | None = None,
) -> dict[str, Any]:
    """Rescue pipeline: YouTube → indir → edit → hook voice → overlay → thumbnail.

    start_sec/end_sec: Compilation videolardan belirli bir segment seçmek için.

    Returns:
        Manifest dict with final_video, thumbnail, title etc.
    """
    # Dizinler
    source_dir = output_base / "source"
    audio_dir = output_base / "audio"
    video_dir = output_base / "video"
    thumbnails_dir = output_base / "thumbnails"
    for d in (source_dir, audio_dir, video_dir, thumbnails_dir):
        d.mkdir(parents=True, exist_ok=True)

    # ── 1. Video indir ──
    logger.info("Adım 1/5: Video indiriliyor...")
    meta = download_video(url, source_dir)

    # ── 2. AI ile dramatik başlık + hook üret ──
    logger.info("Adım 2/5: Başlık ve hook üretiliyor...")
    api_key = (settings.openai_api_key or "").strip()
    if not api_key:
        dramatic_title = meta.title.upper()[:50] + "!"
        hook_text = "Bu anı kaçırmayın."
        logger.warning("OPENAI_API_KEY yok; fallback başlık/hook kullanıldı.")
    else:
        result = generate_title_and_hook(
            video_title=meta.title,
            video_description=meta.description,
            api_key=api_key,
            model=settings.openai_model,
        )
        dramatic_title = result.title
        hook_text = result.hook

    # ── 3. Video edit: 9:16 crop + akıllı örnekleme ──
    logger.info("Adım 3/5: Video editleniyor (9:16 crop + örnekleme)...")
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

    # ── 4. Hook voice üret + mixle ──
    logger.info("Adım 4/5: Hook voice üretiliyor ve mixleniyor...")
    el_key = (settings.elevenlabs_api_key or settings.tts_api_key or "").strip()
    if el_key:
        hook_audio = audio_dir / "hook.mp3"
        generate_voice_mp3(
            script=hook_text,
            output_path=hook_audio,
            api_key=el_key,
            voice_id=settings.elevenlabs_voice_id,
            model_id=settings.elevenlabs_model_id,
        )
        with_hook = video_dir / "with_hook.mp4"
        mix_hook_voice(
            input_path=cropped_path,
            hook_audio_path=hook_audio,
            output_path=with_hook,
            ffmpeg_bin=settings.ffmpeg_path,
            ffprobe_bin=settings.ffprobe_path,
        )
    else:
        logger.warning("ELEVENLABS_API_KEY yok; hook voice atlandı.")
        with_hook = cropped_path

    # ── 5a. Text overlay ekle ──
    final_path = video_dir / "final.mp4"
    add_text_overlay(
        input_path=with_hook,
        output_path=final_path,
        text=dramatic_title,
        display_duration=3.0,
        ffmpeg_bin=settings.ffmpeg_path,
    )

    # ── 5b. Thumbnail üret ──
    logger.info("Adım 5/5: Thumbnail üretiliyor...")
    thumbnail_path = thumbnails_dir / "cover.jpg"
    generate_thumbnail(
        video_path=final_path,
        output_path=thumbnail_path,
        text=dramatic_title,
        ffmpeg_bin=settings.ffmpeg_path,
        ffprobe_bin=settings.ffprobe_path,
    )

    # Ara dosyaları temizle
    for f in (cropped_path, video_dir / "with_hook.mp4"):
        if f != final_path:
            try:
                f.unlink()
            except OSError:
                pass

    # Manifest
    manifest = {
        "mode": "rescue",
        "source_url": url,
        "source_title": meta.title,
        "dramatic_title": dramatic_title,
        "hook_text": hook_text,
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
    logger.info("  Hook: %s", hook_text)

    return manifest
