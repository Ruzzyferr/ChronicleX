from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.settings import Settings
from core.exceptions import MediaPipelineError
from core.media_models import Scene
from modules.render.ffmpeg_runner import (
    burn_subtitles,
    concat_clips,
    ffprobe_duration_seconds,
    mux_audio,
    render_scene_clip,
    write_concat_list,
)
from modules.render.srt_builder import build_srt_for_scenes
from modules.scripting.scene_generator import generate_scenes
from modules.visuals.dalle import generate_image
from modules.voice.elevenlabs import generate_voice_mp3

logger = logging.getLogger(__name__)


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


def run_media_pipeline(
    settings: Settings,
    *,
    script: str,
    paths: MediaPaths,
    topic_id: int | None = None,
) -> dict[str, Any]:
    """Full Faz 3 pipeline: scenes -> images -> voice -> SRT -> FFmpeg -> final.mp4."""
    key = (settings.openai_api_key or "").strip()
    if not key:
        raise MediaPipelineError("OPENAI_API_KEY is required for scene generation.")
    image_key = (settings.image_api_key or settings.openai_api_key or "").strip()
    if not image_key:
        raise MediaPipelineError("OPENAI_API_KEY or IMAGE_API_KEY is required for DALL·E.")
    el = (settings.elevenlabs_api_key or settings.tts_api_key or "").strip()
    if not el:
        raise MediaPipelineError(
            "ELEVENLABS_API_KEY (or TTS_API_KEY) is required for voice generation."
        )

    paths.temp_dir.mkdir(parents=True, exist_ok=True)
    paths.images_dir.mkdir(parents=True, exist_ok=True)
    paths.audio_dir.mkdir(parents=True, exist_ok=True)
    paths.subtitles_dir.mkdir(parents=True, exist_ok=True)
    paths.video_dir.mkdir(parents=True, exist_ok=True)

    scenes = generate_scenes(
        script=script,
        api_key=key,
        model=settings.openai_model,
        temperature=0.0,
    )
    if not scenes:
        raise MediaPipelineError("No scenes generated.")

    image_paths: list[Path] = []
    for s in scenes:
        outp = paths.images_dir / f"scene_{s.scene_id}.png"
        generate_image(
            prompt=s.image_prompt,
            output_path=outp,
            api_key=image_key,
            model=settings.dalle_model,
            size=settings.dalle_size,
        )
        if not outp.is_file() or outp.stat().st_size == 0:
            raise MediaPipelineError(f"Image missing or empty: {outp}")
        image_paths.append(outp)

    voice_path = paths.audio_dir / "voice.mp3"
    generate_voice_mp3(
        script=script,
        output_path=voice_path,
        api_key=el,
        voice_id=settings.elevenlabs_voice_id,
        model_id=settings.elevenlabs_model_id,
    )
    if not voice_path.is_file() or voice_path.stat().st_size == 0:
        raise MediaPipelineError("Voice file missing or empty.")

    audio_duration = ffprobe_duration_seconds(voice_path, settings.ffprobe_path)
    if audio_duration <= 0.5:
        raise MediaPipelineError("Audio duration too short or invalid.")

    seg_times = allocate_scene_times(scenes, audio_duration)
    srt_path = paths.subtitles_dir / "subtitles.srt"
    build_srt_for_scenes(scenes, seg_times, srt_path)

    clip_paths: list[Path] = []
    for s, img, seg in zip(scenes, image_paths, seg_times):
        clip = paths.temp_dir / f"scene_{s.scene_id}.mp4"
        render_scene_clip(
            image_path=img,
            output_mp4=clip,
            scene=s,
            duration_sec=seg,
            ffmpeg_bin=settings.ffmpeg_path,
        )
        clip_paths.append(clip)

    concat_list = paths.temp_dir / "scenes_concat.txt"
    combined = paths.temp_dir / "combined.mp4"
    write_concat_list(clip_paths, concat_list)
    concat_clips(
        list_path=concat_list,
        output_mp4=combined,
        ffmpeg_bin=settings.ffmpeg_path,
    )

    with_audio = paths.temp_dir / "with_audio.mp4"
    mux_audio(
        video_path=combined,
        audio_path=voice_path,
        output_mp4=with_audio,
        ffmpeg_bin=settings.ffmpeg_path,
    )

    final_path = paths.video_dir / "final.mp4"
    burn_subtitles(
        video_path=with_audio,
        srt_path=srt_path,
        output_mp4=final_path,
        ffmpeg_bin=settings.ffmpeg_path,
    )

    manifest = {
        "topic_id": topic_id,
        "final_video": str(final_path.resolve()),
        "audio_path": str(voice_path.resolve()),
        "subtitles_path": str(srt_path.resolve()),
        "image_paths": [str(p.resolve()) for p in image_paths],
        "scene_count": len(scenes),
        "audio_duration_sec": audio_duration,
    }
    manifest_path = paths.video_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info("Media pipeline complete: %s", final_path)

    return {"manifest": manifest, "manifest_path": str(manifest_path)}
