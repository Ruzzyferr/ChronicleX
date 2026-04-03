from __future__ import annotations

import logging
import random
import subprocess
from pathlib import Path

from core.exceptions import MediaPipelineError
from core.media_models import Scene

logger = logging.getLogger(__name__)

FPS = 30


def ffprobe_duration_seconds(media_path: Path, ffprobe_bin: str) -> float:
    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(media_path),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
    except subprocess.CalledProcessError as e:
        raise MediaPipelineError(f"ffprobe failed: {e.stderr}") from e
    except FileNotFoundError as e:
        raise MediaPipelineError(
            f"ffprobe not found ({ffprobe_bin}). Install FFmpeg and set FFPROBE_PATH."
        ) from e
    return float(r.stdout.strip())


def cut_background_clip(
    *,
    bg_video: Path,
    output_mp4: Path,
    duration_sec: float,
    ffmpeg_bin: str,
    ffprobe_bin: str,
) -> None:
    """Arka plan videosundan rastgele bir segment keser ve 1080x1920'ye ölçekler."""
    bg_duration = ffprobe_duration_seconds(bg_video, ffprobe_bin)
    max_start = max(0, bg_duration - duration_sec - 1)
    start = random.uniform(0, max_start) if max_start > 0 else 0.0
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        f"fps={FPS}"
    )
    cmd = [
        ffmpeg_bin,
        "-y",
        "-ss", f"{start:.3f}",
        "-i", str(bg_video.resolve()),
        "-t", f"{duration_sec:.3f}",
        "-vf", vf,
        "-an",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(output_mp4.resolve()),
    ]
    logger.info(
        "ffmpeg background clip -> %s (start=%.1fs, dur=%.1fs)",
        output_mp4.name, start, duration_sec,
    )
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=600)
    except subprocess.CalledProcessError as e:
        raise MediaPipelineError(f"ffmpeg background clip failed: {e.stderr[:500]}") from e


def _zoom_vf(motion: str, frames: int) -> str:
    common = (
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"fps={FPS},"
    )
    if motion == "zoom_out":
        z = (
            f"zoompan=z='max(zoom-0.0025,1.0)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s=1080x1920"
        )
    elif motion == "pan_left":
        z = (
            f"zoompan=z='1.22':x='min(max(0, iw/2-iw/zoom/2-on*2), iw-iw/zoom)':"
            f"y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920"
        )
    elif motion == "pan_right":
        z = (
            f"zoompan=z='1.22':x='max(min(iw-iw/zoom, iw/2-iw/zoom/2+on*2), 0)':"
            f"y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920"
        )
    else:
        z = (
            f"zoompan=z='min(zoom+0.0022,1.45)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s=1080x1920"
        )
    return common + z


def render_scene_clip(
    *,
    image_path: Path,
    output_mp4: Path,
    scene: Scene,
    duration_sec: float,
    ffmpeg_bin: str,
) -> None:
    frames = max(1, int(round(duration_sec * FPS)))
    vf = _zoom_vf(scene.motion, frames)
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin,
        "-y",
        "-loop",
        "1",
        "-i",
        str(image_path.resolve()),
        "-t",
        f"{duration_sec:.3f}",
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-tune",
        "stillimage",
        str(output_mp4.resolve()),
    ]
    logger.info("ffmpeg scene clip -> %s (%.2fs)", output_mp4.name, duration_sec)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=600)
    except subprocess.CalledProcessError as e:
        logger.error("ffmpeg stderr: %s", e.stderr)
        raise MediaPipelineError(f"ffmpeg scene clip failed: {e.stderr[:500]}") from e
    except FileNotFoundError as e:
        raise MediaPipelineError(
            f"ffmpeg not found ({ffmpeg_bin}). Install FFmpeg and set FFMPEG_PATH."
        ) from e
    if proc.stderr:
        logger.debug("ffmpeg stderr: %s", proc.stderr[-800:])


def write_concat_list(clip_paths: list[Path], list_path: Path) -> None:
    lines = []
    for p in clip_paths:
        ap = p.resolve().as_posix().replace("'", "'\\''")
        lines.append(f"file '{ap}'")
    list_path.write_text("\n".join(lines), encoding="utf-8")


def concat_clips(
    *,
    list_path: Path,
    output_mp4: Path,
    ffmpeg_bin: str,
) -> None:
    cmd = [
        ffmpeg_bin,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path.resolve()),
        "-c",
        "copy",
        str(output_mp4.resolve()),
    ]
    logger.info("ffmpeg concat -> %s", output_mp4.name)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=600)
    except subprocess.CalledProcessError as e:
        logger.error("ffmpeg stderr: %s", e.stderr)
        raise MediaPipelineError(f"ffmpeg concat failed: {e.stderr[:500]}") from e
    if r.stderr:
        logger.debug("ffmpeg stderr: %s", r.stderr[-500:])


def mux_audio(
    *,
    video_path: Path,
    audio_path: Path,
    output_mp4: Path,
    ffmpeg_bin: str,
) -> None:
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(video_path.resolve()),
        "-i",
        str(audio_path.resolve()),
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-shortest",
        str(output_mp4.resolve()),
    ]
    logger.info("ffmpeg mux audio -> %s", output_mp4.name)
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=600)
    except subprocess.CalledProcessError as e:
        raise MediaPipelineError(f"ffmpeg mux failed: {e.stderr[:500]}") from e


def burn_subtitles(
    *,
    video_path: Path,
    subtitle_path: Path,
    output_mp4: Path,
    ffmpeg_bin: str,
) -> None:
    s = subtitle_path.resolve().as_posix()
    if s[1] == ":":
        s_esc = s.replace("\\", "/").replace(":", r"\\:")
    else:
        s_esc = s.replace("\\", "/")
    vf = f"subtitles={s_esc}"
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(video_path.resolve()),
        "-vf",
        vf,
        "-c:a",
        "copy",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(output_mp4.resolve()),
    ]
    logger.info("ffmpeg burn subtitles -> %s", output_mp4.name)
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=900)
    except subprocess.CalledProcessError as e:
        raise MediaPipelineError(f"ffmpeg subtitles failed: {e.stderr[:500]}") from e
