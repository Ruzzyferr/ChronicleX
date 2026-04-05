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


def _crop_filter() -> str:
    """9:16 crop filtresi: ortadan kırp."""
    return (
        f"crop=ih*9/16:ih,"
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
        f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:black,"
        f"fps={FPS}"
    )


def _cut_single_segment(
    *,
    input_path: Path,
    output_path: Path,
    start: float,
    duration: float,
    vf: str,
    ffmpeg_bin: str,
) -> None:
    """Videodan tek bir segment kes (crop dahil)."""
    cmd = [
        ffmpeg_bin, "-y",
        "-ss", f"{start:.2f}",
        "-i", str(input_path),
        "-t", f"{duration:.2f}",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(output_path),
    ]
    _run_ffmpeg(cmd, f"segment_{start:.0f}")


def crop_and_trim(
    *,
    input_path: Path,
    output_path: Path,
    target_duration: float = 59.0,
    segment_length: float = 10.0,
    start_sec: float | None = None,
    end_sec: float | None = None,
    ffmpeg_bin: str = "ffmpeg",
    ffprobe_bin: str = "ffprobe",
) -> None:
    """Videoyu 9:16 crop + hedef süreye kes. Orijinal ses korunur.

    start_sec/end_sec verilirse o aralığı direkt kullanır (compilation videolar).

    Video hedef süreden uzunsa akıllı örnekleme yapar:
    - Videoyu segment_length saniyelik parçalara böler
    - Eşit aralıklarla segment seçer (baştan, ortadan, sondan)
    - Seçilen segmentleri birleştirip hedef süreye ulaşır
    Böylece videonun tamamının özeti korunur.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total_dur = ffprobe_duration(input_path, ffprobe_bin)

    if total_dur <= 0:
        raise MediaPipelineError(f"Video süresi alınamadı: {input_path}")

    vf = _crop_filter()

    # ── Manuel segment seçimi ──
    if start_sec is not None or end_sec is not None:
        s = max(0.0, start_sec or 0.0)
        e = min(end_sec or total_dur, total_dur)
        dur = min(e - s, target_duration)
        if dur < 5:
            raise MediaPipelineError(
                f"Seçilen segment çok kısa: {dur:.1f}s (start={s}, end={e})"
            )
        logger.info("Manuel segment: %.1fs - %.1fs (%.1fs)", s, e, dur)
        cmd = [
            ffmpeg_bin, "-y",
            "-ss", f"{s:.2f}",
            "-i", str(input_path),
            "-t", f"{dur:.2f}",
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(output_path),
        ]
        _run_ffmpeg(cmd, "crop_and_trim_manual")
        logger.info("Video kırpıldı (manuel): %.1fs, 9:16 format", dur)
        return

    # ── Video hedef süreye sığıyorsa direkt kes ──
    if total_dur <= target_duration:
        cmd = [
            ffmpeg_bin, "-y",
            "-i", str(input_path),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(output_path),
        ]
        _run_ffmpeg(cmd, "crop_short_video")
        logger.info("Video kırpıldı (kısa): %.1fs, 9:16 format", total_dur)
        return

    # ── Akıllı örnekleme: uzun videodan eşit aralıklı segmentler al ──
    # İlk ve son 10 saniyeyi atla (intro/outro), kullanılabilir aralıktan örnekle
    # İlk segment = videonun 2. segmenti (10-20s), son segment = sondan 2. segment
    skip = segment_length  # ilk ve son 10sn atlanır
    usable_start = skip
    usable_end = total_dur - skip
    usable_dur = usable_end - usable_start

    if usable_dur < target_duration:
        # Video çok kısa, intro/outro atlama yapma, direkt kes
        cmd = [
            ffmpeg_bin, "-y",
            "-i", str(input_path),
            "-t", f"{target_duration:.2f}",
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(output_path),
        ]
        _run_ffmpeg(cmd, "crop_and_trim_simple")
        logger.info("Video kırpıldı: %.1fs, 9:16 format", target_duration)
        return

    segments_needed = max(2, int(target_duration / segment_length))  # 60/10 = 6
    usable_segments = int(usable_dur / segment_length)               # (180-20)/10 = 16

    if usable_segments <= segments_needed:
        cmd = [
            ffmpeg_bin, "-y",
            "-ss", f"{usable_start:.2f}",
            "-i", str(input_path),
            "-t", f"{target_duration:.2f}",
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(output_path),
        ]
        _run_ffmpeg(cmd, "crop_and_trim_simple")
        logger.info("Video kırpıldı: %.1fs, 9:16 format", target_duration)
        return

    # İlk (0) ve son (usable_segments-1) sabit, aradaki eşit dağıtılır
    last_usable = usable_segments - 1
    pick_indexes = [0]
    middle_count = segments_needed - 2
    if middle_count > 0 and last_usable > 1:
        step = (last_usable - 1) / (middle_count + 1)
        for i in range(1, middle_count + 1):
            idx = int(round(i * step))
            if idx not in (0, last_usable):
                pick_indexes.append(idx)
    pick_indexes.append(last_usable)
    pick_indexes = sorted(set(pick_indexes))

    # Eksik segment varsa tamamlamak için son segmenti uzat
    actual_count = len(pick_indexes)
    deficit = target_duration - (actual_count * segment_length)

    logger.info(
        "Akıllı örnekleme: %d segmentten %d tanesi seçildi (ilk + son sabit)",
        usable_segments, actual_count,
    )
    logger.info("Seçilen segmentler: %s", pick_indexes)

    # Her segmenti kes
    temp_dir = output_path.parent / "_rescue_segments"
    temp_dir.mkdir(parents=True, exist_ok=True)
    segment_files: list[Path] = []

    for i, seg_idx in enumerate(pick_indexes):
        seg_start = usable_start + (seg_idx * segment_length)
        # Son segment: eksik süreyi tamamlamak için uzat
        is_last = (i == actual_count - 1)
        seg_dur = segment_length + deficit if is_last and deficit > 0 else segment_length
        # Videonun sonunu aşmasın
        seg_dur = min(seg_dur, total_dur - seg_start)
        seg_file = temp_dir / f"seg_{i:03d}.mp4"
        _cut_single_segment(
            input_path=input_path,
            output_path=seg_file,
            start=seg_start,
            duration=seg_dur,
            vf=vf,
            ffmpeg_bin=ffmpeg_bin,
        )
        segment_files.append(seg_file)

    # Concat listesi yaz
    concat_list = temp_dir / "concat.txt"
    lines = [f"file '{f.name}'" for f in segment_files]
    concat_list.write_text("\n".join(lines), encoding="utf-8")

    # Birleştir
    cmd = [
        ffmpeg_bin, "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(output_path),
    ]
    _run_ffmpeg(cmd, "concat_segments")

    # Temp temizle
    import shutil
    try:
        shutil.rmtree(temp_dir)
    except OSError:
        pass

    actual = len(pick_indexes) * segment_length
    logger.info(
        "Video örneklendi: %d segment x %.0fs = %.0fs, 9:16 format",
        len(pick_indexes), segment_length, actual,
    )


def _write_overlay_ass(
    output_path: Path,
    text: str,
    display_duration: float = 3.0,
) -> None:
    """Dramatik text overlay için ASS altyazı dosyası oluştur.

    drawtext yerine ASS kullanıyoruz çünkü:
    - Windows'ta drawtext Türkçe karakterlerle crash yapıyor
    - ASS daha zengin stil desteği sunuyor (outline, shadow, fade)
    """
    # ASS zaman formatı: H:MM:SS.CC
    def _fmt(sec: float) -> str:
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = sec % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    start = _fmt(0)
    end = _fmt(display_duration)

    # Fade: \fad(fade_in_ms, fade_out_ms)
    fade_in_ms = 500
    fade_out_ms = 500

    ass_content = f"""[Script Info]
Title: Rescue Overlay
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Overlay,Arial,64,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,4,2,8,40,40,320,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,{start},{end},Overlay,,0,0,0,,{{\\fad({fade_in_ms},{fade_out_ms})}}{text}
"""
    output_path.write_text(ass_content, encoding="utf-8-sig")


def _escape_ass_path(path: Path) -> str:
    """Windows'ta ASS dosya yolundaki C: → C\\: dönüşümü."""
    s = str(path).replace("\\", "/")
    # Windows drive letter: C: → C\:
    if len(s) >= 2 and s[1] == ":":
        s = s[0] + "\\:" + s[2:]
    return s


def add_text_overlay(
    *,
    input_path: Path,
    output_path: Path,
    text: str,
    display_duration: float = 3.0,
    ffmpeg_bin: str = "ffmpeg",
) -> None:
    """Videonun başına dramatik text overlay ekle (fade-in/out ile).

    ASS altyazı dosyası kullanır (drawtext Windows'ta Türkçe karakterlerle crash yapıyor).
    Kalın beyaz yazı, siyah outline, ekranın üst kısmında, ortalanmış.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ASS dosyasını video'nun yanına yaz
    ass_path = output_path.parent / "overlay.ass"
    _write_overlay_ass(ass_path, text, display_duration)

    escaped_ass = _escape_ass_path(ass_path)
    vf = f"ass='{escaped_ass}'"

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

    # ASS dosyasını temizle
    try:
        ass_path.unlink()
    except OSError:
        pass

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
    ASS overlay ile kırmızı outline'lı kalın beyaz yazı.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total_dur = ffprobe_duration(video_path, ffprobe_bin)
    seek_point = max(1.0, total_dur * 0.3)

    # Thumbnail için ASS: kırmızı outline, kalın, ortalı
    ass_path = output_path.parent / "thumb_overlay.ass"
    ass_content = f"""[Script Info]
Title: Thumbnail Overlay
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Thumb,Arial,72,&H00FFFFFF,&H000000FF,&H000000FF,&H80000000,-1,0,0,0,100,100,2,0,1,5,3,8,40,40,400,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:01.00,Thumb,,0,0,0,,{text}
"""
    ass_path.write_text(ass_content, encoding="utf-8-sig")
    escaped_ass = _escape_ass_path(ass_path)

    # Önce frame çek, sonra ASS overlay ekle
    raw_frame = output_path.parent / "thumb_raw.jpg"
    cmd_frame = [
        ffmpeg_bin, "-y",
        "-ss", f"{seek_point:.2f}",
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        str(raw_frame),
    ]
    _run_ffmpeg(cmd_frame, "thumbnail_frame")

    # ASS overlay ekle
    cmd_overlay = [
        ffmpeg_bin, "-y",
        "-i", str(raw_frame),
        "-vf", f"ass='{escaped_ass}'",
        "-q:v", "2",
        str(output_path),
    ]
    _run_ffmpeg(cmd_overlay, "thumbnail_overlay")

    # Temizle
    for f in (ass_path, raw_frame):
        try:
            f.unlink()
        except OSError:
            pass

    logger.info("Thumbnail oluşturuldu: %s", output_path)
