"""FFmpeg ile rescue video editlme: crop, trim, text overlay, thumbnail."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from core.exceptions import MediaPipelineError

logger = logging.getLogger(__name__)

FPS = 30
TARGET_W = 1080
TARGET_H = 1920


def _run_ffmpeg(cmd: list[str], description: str) -> None:
    """FFmpeg komutunu çalıştır, hata varsa MediaPipelineError fırlat."""
    logger.debug("FFmpeg: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        logger.error("FFmpeg hatası (%s): %s", description, result.stderr[-500:] if result.stderr else "")
        raise MediaPipelineError(f"FFmpeg başarısız ({description}): return code {result.returncode}")


def ffprobe_duration(video_path: Path, ffprobe_bin: str = "ffprobe") -> float:
    """Video süresini saniye cinsinden döndür."""
    cmd = [
        ffprobe_bin, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def crop_and_trim(
    *,
    input_path: Path,
    output_path: Path,
    target_duration: float = 59.0,
    start_sec: float | None = None,
    end_sec: float | None = None,
    ffmpeg_bin: str = "ffmpeg",
    ffprobe_bin: str = "ffprobe",
) -> None:
    """Videoyu 9:16 crop + hedef süreye kes. Orijinal ses korunur.

    start_sec/end_sec verilirse o aralığı kullanır (compilation videolar için).
    Verilmezse videonun ilk %10'unu atlayıp ortadan başlar.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total_dur = ffprobe_duration(input_path, ffprobe_bin)

    if total_dur <= 0:
        raise MediaPipelineError(f"Video süresi alınamadı: {input_path}")

    if start_sec is not None or end_sec is not None:
        # Manuel segment seçimi (compilation videolar için)
        start_offset = max(0.0, start_sec or 0.0)
        clip_end = min(end_sec or total_dur, total_dur)
        actual_duration = min(clip_end - start_offset, target_duration)
        if actual_duration < 5:
            raise MediaPipelineError(
                f"Seçilen segment çok kısa: {actual_duration:.1f}s "
                f"(start={start_offset}, end={clip_end})"
            )
        logger.info("Manuel segment: %.1fs - %.1fs (%.1fs)", start_offset, clip_end, actual_duration)
    else:
        # Otomatik: ilk %10'u atla (intro/logo)
        start_offset = min(total_dur * 0.1, 10.0)
        available = total_dur - start_offset
        actual_duration = min(target_duration, available)

        if actual_duration < 10:
            start_offset = 0
            actual_duration = min(target_duration, total_dur)

    # 9:16 crop filtresi: ortadan kırp
    vf = (
        f"crop=ih*9/16:ih,"
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
        f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:black,"
        f"fps={FPS}"
    )

    cmd = [
        ffmpeg_bin, "-y",
        "-ss", f"{start_offset:.2f}",
        "-i", str(input_path),
        "-t", f"{actual_duration:.2f}",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(output_path),
    ]
    _run_ffmpeg(cmd, "crop_and_trim")
    logger.info("Video kırpıldı: %.1fs, 9:16 format", actual_duration)


def add_text_overlay(
    *,
    input_path: Path,
    output_path: Path,
    text: str,
    display_duration: float = 3.0,
    ffmpeg_bin: str = "ffmpeg",
) -> None:
    """Videonun başına dramatik text overlay ekle (fade-in/out ile).

    Kalın beyaz yazı, siyah stroke, ekranın üst 1/3'ünde, ortalanmış.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # FFmpeg drawtext için özel karakter escape
    escaped = text.replace("'", "'\\''").replace(":", "\\:")

    # Text overlay filtresi: fade-in 0.5s, display, fade-out 0.5s
    fade_in = 0.5
    fade_out = 0.5
    end_time = display_duration

    vf = (
        f"drawtext="
        f"text='{escaped}':"
        f"fontsize=56:"
        f"fontcolor=white:"
        f"borderw=4:"
        f"bordercolor=black:"
        f"x=(w-text_w)/2:"
        f"y=h/5:"
        f"alpha='if(lt(t,{fade_in}),t/{fade_in},if(lt(t,{end_time - fade_out}),1,(({end_time}-t)/{fade_out})))'"
    )

    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(input_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(output_path),
    ]
    _run_ffmpeg(cmd, "text_overlay")
    logger.info("Text overlay eklendi: %s", text)


def generate_thumbnail(
    *,
    video_path: Path,
    output_path: Path,
    text: str,
    ffmpeg_bin: str = "ffmpeg",
    ffprobe_bin: str = "ffprobe",
) -> None:
    """Videodan dikkat çekici bir frame çekip üstüne başlık yazısı ekle.

    Videonun %30'undaki frame'i çeker (genellikle ilginç bir sahne).
    Kırmızı-turuncu gradient arka planlı kalın yazı.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total_dur = ffprobe_duration(video_path, ffprobe_bin)
    seek_point = max(1.0, total_dur * 0.3)

    escaped = text.replace("'", "'\\''").replace(":", "\\:")

    # Frame çek + üstüne kalın kırmızı yazı ekle
    vf = (
        f"drawtext="
        f"text='{escaped}':"
        f"fontsize=64:"
        f"fontcolor=white:"
        f"borderw=5:"
        f"bordercolor=red:"
        f"x=(w-text_w)/2:"
        f"y=h/4"
    )

    cmd = [
        ffmpeg_bin, "-y",
        "-ss", f"{seek_point:.2f}",
        "-i", str(video_path),
        "-vframes", "1",
        "-vf", vf,
        "-q:v", "2",
        str(output_path),
    ]
    _run_ffmpeg(cmd, "thumbnail")
    logger.info("Thumbnail oluşturuldu: %s", output_path)
