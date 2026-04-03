from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.settings import Settings, project_root
from core.exceptions import MediaPipelineError
from core.media_models import Scene
from modules.render.ffmpeg_runner import (
    burn_subtitles,
    concat_clips,
    cut_background_clip,
    ffprobe_duration_seconds,
    mux_audio,
    render_scene_clip,
    write_concat_list,
)
from modules.render.ass_builder import build_ass_for_scenes
from modules.scripting.scene_generator import generate_scenes, normalize_scenes
from modules.scripting.topic_narration import topic_scenes_json_path
from modules.visuals.dalle import generate_image
from modules.voice.elevenlabs import generate_voice_mp3

logger = logging.getLogger(__name__)

_MIN_BYTES_PNG = 512
_MIN_BYTES_MP3 = 400
_MIN_BYTES_MP4 = 1024


@dataclass
class MediaPaths:
    project_root: Path
    output_base: Path
    temp_dir: Path
    images_dir: Path
    audio_dir: Path
    subtitles_dir: Path
    video_dir: Path

    @classmethod
    def from_output_base(cls, project_root: Path, output_base: Path) -> MediaPaths:
        return cls(
            project_root=project_root,
            output_base=output_base,
            temp_dir=project_root / "temp",
            images_dir=output_base / "images",
            audio_dir=output_base / "audio",
            subtitles_dir=output_base / "subtitles",
            video_dir=output_base / "video",
        )


def allocate_scene_times(scenes: list[Scene], total_seconds: float) -> list[float]:
    w = sum(s.duration for s in scenes)
    if w <= 0:
        raise ValueError("invalid scene durations")
    return [total_seconds * (s.duration / w) for s in scenes]


def _scenes_json_path(output_base: Path) -> Path:
    return output_base / "scenes.json"


def _render_cache_dir(output_base: Path) -> Path:
    return output_base / "render_cache"


def _load_scenes_json(path: Path) -> list[Scene]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise MediaPipelineError(f"scenes.json okunamadı: {path}") from e
    if isinstance(raw, dict) and "scenes" in raw:
        raw = raw["scenes"]
    if not isinstance(raw, list) or not raw:
        raise MediaPipelineError("scenes.json boş veya geçersiz.")
    return [Scene.model_validate(item) for item in raw]


def _save_scenes_json(path: Path, scenes: list[Scene]) -> None:
    path.write_text(
        json.dumps([s.model_dump() for s in scenes], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _usable(path: Path, min_size: int) -> bool:
    return path.is_file() and path.stat().st_size >= min_size


def _find_background_video(bg_dir: str) -> Path | None:
    """assets/backgrounds/ klasöründen rastgele bir mp4 seç."""
    bg_path = project_root() / bg_dir
    if not bg_path.is_dir():
        return None
    videos = list(bg_path.glob("*.mp4")) + list(bg_path.glob("*.mkv")) + list(bg_path.glob("*.mov"))
    if not videos:
        return None
    return random.choice(videos)


def run_media_pipeline(
    settings: Settings,
    *,
    script: str,
    paths: MediaPaths,
    topic_id: int | None = None,
    resume: bool = False,
) -> dict[str, Any]:
    """Sahne → görsel → ses → SRT → FFmpeg → final.mp4. resume=True iken mevcut dosyalar atlanır."""
    scenes_path = _scenes_json_path(paths.output_base)
    render_cache = _render_cache_dir(paths.output_base)

    paths.temp_dir.mkdir(parents=True, exist_ok=True)
    paths.images_dir.mkdir(parents=True, exist_ok=True)
    paths.audio_dir.mkdir(parents=True, exist_ok=True)
    paths.subtitles_dir.mkdir(parents=True, exist_ok=True)
    paths.video_dir.mkdir(parents=True, exist_ok=True)
    render_cache.mkdir(parents=True, exist_ok=True)

    topic_scenes_file = topic_scenes_json_path(paths.output_base)

    if resume and scenes_path.is_file():
        scenes = _load_scenes_json(scenes_path)
        logger.info("Resume: %s sahne scenes.json içinden yüklendi.", len(scenes))
    elif topic_scenes_file.is_file():
        try:
            raw = json.loads(topic_scenes_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise MediaPipelineError(f"topic_scenes.json okunamadı: {topic_scenes_file}") from e
        if isinstance(raw, dict) and "scenes" in raw:
            raw = raw["scenes"]
        if not isinstance(raw, list) or not raw:
            raise MediaPipelineError("topic_scenes.json boş veya geçersiz.")
        parsed = [Scene.model_validate(item) for item in raw]
        scenes = normalize_scenes(parsed)
        _save_scenes_json(scenes_path, scenes)
        try:
            topic_scenes_file.unlink()
        except OSError:
            pass
        logger.info(
            "Konu adımından gelen %s sahne kullanıldı (OpenAI metin + DALL·E prompt).",
            len(scenes),
        )
    elif not resume:
        key = (settings.openai_api_key or "").strip()
        if not key:
            raise MediaPipelineError("OPENAI_API_KEY is required for scene generation.")
        scenes = generate_scenes(
            script=script,
            api_key=key,
            model=settings.openai_model,
            temperature=0.0,
        )
        if not scenes:
            raise MediaPipelineError("No scenes generated.")
        _save_scenes_json(scenes_path, scenes)
    else:
        raise MediaPipelineError(
            "Resume için scenes.json yok; aynı üretim klasöründe devam edilemiyor."
        )

    if not scenes:
        raise MediaPipelineError("No scenes.")

    el = (settings.elevenlabs_api_key or settings.tts_api_key or "").strip()

    # ── 1. Ses üret ──
    voice_path = paths.audio_dir / "voice.mp3"
    if resume and _usable(voice_path, _MIN_BYTES_MP3):
        logger.info("Resume: ses dosyası atlandı.")
    else:
        if not el:
            raise MediaPipelineError(
                "ELEVENLABS_API_KEY (or TTS_API_KEY) is required for voice generation."
            )
        generate_voice_mp3(
            script=script,
            output_path=voice_path,
            api_key=el,
            voice_id=settings.elevenlabs_voice_id,
            model_id=settings.elevenlabs_model_id,
        )
        if not _usable(voice_path, _MIN_BYTES_MP3):
            raise MediaPipelineError("Voice file missing or empty.")

    audio_duration = ffprobe_duration_seconds(voice_path, settings.ffprobe_path)
    if audio_duration <= 0.5:
        raise MediaPipelineError("Audio duration too short or invalid.")

    # ── 2. Altyazı oluştur ──
    seg_times = allocate_scene_times(scenes, audio_duration)
    ass_path = paths.subtitles_dir / "subtitles.ass"
    build_ass_for_scenes(scenes, seg_times, ass_path)

    # ── 3. Video oluştur ──
    combined = render_cache / "combined.mp4"
    with_audio = render_cache / "with_audio.mp4"
    final_path = paths.video_dir / "final.mp4"

    bg_video = _find_background_video(settings.background_video_dir)
    use_background = bg_video is not None

    if resume and _usable(final_path, 10_000):
        logger.info("Resume: final.mp4 zaten var, yeniden üretilmedi.")
    elif use_background:
        # ── Gameplay arka plan modu ──
        logger.info("Gameplay arka plan modu: %s", bg_video.name)
        if not (resume and _usable(combined, _MIN_BYTES_MP4)):
            cut_background_clip(
                bg_video=bg_video,
                output_mp4=combined,
                duration_sec=audio_duration,
                ffmpeg_bin=settings.ffmpeg_path,
                ffprobe_bin=settings.ffprobe_path,
            )

        if not (resume and _usable(with_audio, _MIN_BYTES_MP4)):
            mux_audio(
                video_path=combined,
                audio_path=voice_path,
                output_mp4=with_audio,
                ffmpeg_bin=settings.ffmpeg_path,
            )

        burn_subtitles(
            video_path=with_audio,
            subtitle_path=ass_path,
            output_mp4=final_path,
            ffmpeg_bin=settings.ffmpeg_path,
        )
    else:
        # ── Fallback: DALL·E görsel modu ──
        logger.info("DALL·E görsel modu (arka plan videosu bulunamadı).")
        image_key = (settings.image_api_key or settings.openai_api_key or "").strip()

        image_paths: list[Path] = []
        for s in scenes:
            outp = paths.images_dir / f"scene_{s.scene_id}.png"
            if resume and _usable(outp, _MIN_BYTES_PNG):
                logger.info("Resume: sahne %s görseli atlandı.", s.scene_id)
            else:
                if not image_key:
                    raise MediaPipelineError(
                        "OPENAI_API_KEY or IMAGE_API_KEY is required for DALL·E."
                    )
                generate_image(
                    prompt=s.image_prompt,
                    output_path=outp,
                    api_key=image_key,
                    model=settings.dalle_model,
                    size=settings.dalle_size,
                )
                if not _usable(outp, _MIN_BYTES_PNG):
                    raise MediaPipelineError(f"Image missing or empty: {outp}")
            image_paths.append(outp)

        clip_paths: list[Path] = []
        for s, img, seg in zip(scenes, image_paths, seg_times, strict=True):
            clip = render_cache / f"scene_{s.scene_id}.mp4"
            if resume and _usable(clip, _MIN_BYTES_MP4):
                logger.info("Resume: sahne %s klibi atlandı.", s.scene_id)
            else:
                render_scene_clip(
                    image_path=img,
                    output_mp4=clip,
                    scene=s,
                    duration_sec=seg,
                    ffmpeg_bin=settings.ffmpeg_path,
                )
            clip_paths.append(clip)

        rebuilt_combined = False
        if not (resume and _usable(combined, _MIN_BYTES_MP4)):
            concat_list = render_cache / "concat.txt"
            write_concat_list(clip_paths, concat_list)
            concat_clips(
                list_path=concat_list,
                output_mp4=combined,
                ffmpeg_bin=settings.ffmpeg_path,
            )
            rebuilt_combined = True

        if rebuilt_combined or not (resume and _usable(with_audio, _MIN_BYTES_MP4)):
            mux_audio(
                video_path=combined,
                audio_path=voice_path,
                output_mp4=with_audio,
                ffmpeg_bin=settings.ffmpeg_path,
            )

        burn_subtitles(
            video_path=with_audio,
            subtitle_path=ass_path,
            output_mp4=final_path,
            ffmpeg_bin=settings.ffmpeg_path,
        )

    manifest = {
        "topic_id": topic_id,
        "final_video": str(final_path.resolve()),
        "audio_path": str(voice_path.resolve()),
        "subtitles_path": str(ass_path.resolve()),
        "background_mode": "gameplay" if use_background else "dalle",
        "scene_count": len(scenes),
        "audio_duration_sec": audio_duration,
        "resume_used": resume,
    }
    manifest_path = paths.video_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info("Media pipeline complete: %s", final_path)

    return {"manifest": manifest, "manifest_path": str(manifest_path)}
