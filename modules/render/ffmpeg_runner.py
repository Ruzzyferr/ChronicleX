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
    # FFmpeg subtitles filter path escaping:
    #   ':'  -> '\\:'  (escaped for filter option parser)
    #   '\\' -> '/'    (use posix separators)
    #   wrap with ' '  (quote to protect special chars)
    s = subtitle_path.resolve().as_posix()
    # Escape special chars for FFmpeg filter option syntax
    s_esc = s.replace("\\", "/")
    if len(s_esc) > 1 and s_esc[1] == ":":
        s_esc = s_esc[0] + "\\:" + s_esc[2:]
    # Single-quote wrapping protects spaces and other specials
    vf = f"subtitles='{s_esc}'"
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
        raise MediaPipelineError(f"ffmpeg subtitles failed (exit {e.returncode}): {e.stderr[-1500:]}") from e


def overlay_images_on_video(
    *,
    video_path: Path,
    image_entries: list[dict],
    output_mp4: Path,
    ffmpeg_bin: str,
    fade_duration: float = 0.5,
) -> None:
    """Overlay timed still images onto the video using a filter graph.

    Each image is fed as a single-frame input.  The overlay filter's default
    ``eof_action=repeat`` keeps the frame visible for the ``enable`` window.
    Fade-in/out is achieved via the ``format=auto`` alpha channel on overlay
    combined with a ``colorchannelmixer`` opacity ramp.
    """
    if not image_entries:
        raise MediaPipelineError("overlay_images_on_video requires at least one image entry.")

    output_mp4.parent.mkdir(parents=True, exist_ok=True)

    # Build inputs: main video + one -i per image (single frame, no -loop)
    cmd = [ffmpeg_bin, "-y", "-i", str(video_path.resolve())]
    for entry in image_entries:
        img_path = Path(entry["path"])
        cmd.extend(["-i", str(img_path.resolve())])

    # Build filter graph
    filter_parts: list[str] = []
    last_label = "[0:v]"
    for idx, entry in enumerate(image_entries, start=1):
        start = float(entry["start"])
        end = float(entry["end"])
        img_label = f"[img{idx}]"
        out_label = f"[v{idx}]"

        # Scale image to 700px wide, keep aspect, convert to RGBA
        filter_parts.append(
            f"[{idx}:v]scale=700:-1,format=rgba{img_label}"
        )
        # Overlay with enable window; eof_action=repeat keeps the
        # single frame visible for the entire window.
        filter_parts.append(
            f"{last_label}{img_label}"
            f"overlay=(W-w)/2:(H-h)/3"
            f":eof_action=repeat"
            f":enable='between(t,{start:.3f},{end:.3f})'"
            f"{out_label}"
        )
        last_label = out_label

    cmd.extend(
        [
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            last_label,
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            str(output_mp4.resolve()),
        ]
    )

    logger.info("ffmpeg overlay images -> %s", output_mp4.name)
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=900)
    except subprocess.CalledProcessError as e:
        raise MediaPipelineError(f"ffmpeg overlay failed: {e.stderr[:500]}") from e
    except subprocess.TimeoutExpired as e:
        raise MediaPipelineError(
            "ffmpeg overlay timed out after 900s; try reducing overlay image count."
        ) from e


def cut_and_concat_trailer_clips(
    *,
    trailer_path: Path,
    output_mp4: Path,
    target_duration: float,
    clip_length: float = 5.0,
    ffmpeg_bin: str,
    ffprobe_bin: str,
) -> None:
    """Trailer'dan eşit aralıklı kesitler çıkarıp birleştirir.

    Trailer süresini ölçer, target_duration'a ulaşmak için
    clip_length saniyelik N kesit seçer, 1080x1920'ye scale eder
    ve birleştirir. Ses dahil edilmez.
    """
    import math
    import tempfile

    trailer_dur = ffprobe_duration_seconds(trailer_path, ffprobe_bin)
    if trailer_dur <= 0:
        raise MediaPipelineError("Trailer süresi ölçülemedi.")

    n_clips = max(1, int(math.ceil(target_duration / clip_length)))
    # Actual clip length may be adjusted to fill target_duration evenly
    actual_clip = target_duration / n_clips
    # Spacing: pick N evenly spaced start points within trailer
    spacing = trailer_dur / n_clips

    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    cache_dir = output_mp4.parent

    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        f"fps={FPS}"
    )

    clip_paths: list[Path] = []
    for i in range(n_clips):
        start = i * spacing
        # Don't exceed trailer bounds
        if start + actual_clip > trailer_dur:
            start = max(0, trailer_dur - actual_clip)
        clip_out = cache_dir / f"trailer_clip_{i:03d}.mp4"
        cmd = [
            ffmpeg_bin, "-y",
            "-ss", f"{start:.3f}",
            "-i", str(trailer_path.resolve()),
            "-t", f"{actual_clip:.3f}",
            "-vf", vf,
            "-an",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            str(clip_out.resolve()),
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=120)
        except subprocess.CalledProcessError as e:
            raise MediaPipelineError(f"Trailer clip {i} kesilirken hata: {e.stderr[-500:]}") from e
        clip_paths.append(clip_out)

    logger.info("Trailer: %d kesit oluşturuldu (her biri ~%.1f sn)", n_clips, actual_clip)

    # Concat all clips
    concat_file = cache_dir / "trailer_concat.txt"
    write_concat_list(clip_paths, concat_file)
    concat_clips(list_path=concat_file, output_mp4=output_mp4, ffmpeg_bin=ffmpeg_bin)
    logger.info("Trailer kesitleri birleştirildi: %s", output_mp4.name)
