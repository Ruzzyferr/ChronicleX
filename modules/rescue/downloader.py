"""YouTube video indirme ve metadata çekme (yt-dlp)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class VideoMeta:
    title: str
    description: str
    duration: float
    video_path: Path


def download_video(url: str, output_dir: Path) -> VideoMeta:
    """YouTube videosunu indir, metadata ile birlikte döndür."""
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError("yt-dlp yüklü değil. Çalıştır: pip install yt-dlp") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "source.mp4"

    ydl_opts = {
        "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
        "outtmpl": str(output_path),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
    }

    logger.info("YouTube video indiriliyor: %s", url)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    if info is None:
        raise RuntimeError(f"Video bilgisi alınamadı: {url}")

    title = info.get("title", "")
    description = info.get("description", "")
    duration = float(info.get("duration", 0))

    # yt-dlp bazen farklı uzantı ekleyebilir
    if not output_path.is_file():
        for p in output_dir.glob("source.*"):
            if p.suffix in (".mp4", ".mkv", ".webm") and p.stat().st_size > 1024:
                output_path = p
                break

    if not output_path.is_file() or output_path.stat().st_size < 1024:
        raise RuntimeError(f"Video indirilemedi veya dosya çok küçük: {output_path}")

    logger.info(
        "Video indirildi: '%s' (%.0f sn, %.1f MB)",
        title, duration, output_path.stat().st_size / 1e6,
    )

    return VideoMeta(
        title=title,
        description=description[:3000],
        duration=duration,
        video_path=output_path,
    )


def get_video_metadata(url: str) -> dict[str, str | float]:
    """Sadece metadata çek (indirmeden)."""
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError("yt-dlp yüklü değil.") from exc

    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if info is None:
        raise RuntimeError(f"Metadata alınamadı: {url}")

    return {
        "title": info.get("title", ""),
        "description": (info.get("description", "") or "")[:3000],
        "duration": float(info.get("duration", 0)),
    }
