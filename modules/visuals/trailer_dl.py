"""YouTube trailer arama ve indirme (yt-dlp)."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def search_and_download_trailer(
    topic: str,
    output_dir: Path,
    max_duration: int = 300,
) -> Path | None:
    """Search YouTube for '{topic} official trailer' and download the best match.

    Returns the downloaded file path, or None on failure.
    Video only (no audio), max 720p, mp4 format.
    """
    try:
        import yt_dlp
    except ImportError:
        logger.error("yt-dlp is not installed. Run: pip install yt-dlp")
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "trailer.mp4"

    query = f"{topic} official trailer"
    logger.info("YouTube trailer araması: '%s'", query)

    ydl_opts = {
        "format": "bestvideo[height<=720][ext=mp4]/bestvideo[height<=720]/best[height<=720]",
        "outtmpl": str(output_path),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "match_filter": yt_dlp.utils.match_filter_func(f"duration <= {max_duration}"),
        "default_search": "ytsearch5",
        "merge_output_format": "mp4",
        "postprocessors": [],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch5:{query}", download=False)

            if not info or "entries" not in info:
                logger.warning("YouTube aramasında sonuç bulunamadı: '%s'", query)
                return None

            entries = [e for e in info["entries"] if e is not None]
            if not entries:
                logger.warning("Uygun trailer bulunamadı: '%s'", query)
                return None

            # Pick the first result that has a reasonable duration
            chosen = None
            for entry in entries:
                dur = entry.get("duration") or 0
                if 30 <= dur <= max_duration:
                    chosen = entry
                    break
            if chosen is None:
                chosen = entries[0]

            video_url = chosen.get("webpage_url") or chosen.get("url") or chosen.get("id")
            title = chosen.get("title", "unknown")
            duration = chosen.get("duration", 0)
            logger.info(
                "Trailer seçildi: '%s' (%.0f sn) — %s",
                title, duration, video_url,
            )

            # Download the chosen video
            dl_opts = dict(ydl_opts)
            dl_opts.pop("default_search", None)
            dl_opts.pop("match_filter", None)
            with yt_dlp.YoutubeDL(dl_opts) as ydl2:
                ydl2.download([video_url])

        if output_path.is_file() and output_path.stat().st_size > 1024:
            logger.info("Trailer indirildi: %s (%.1f MB)", output_path.name, output_path.stat().st_size / 1e6)
            return output_path

        # yt-dlp may add format extension; check for variants
        for p in output_dir.glob("trailer.*"):
            if p.suffix in (".mp4", ".mkv", ".webm") and p.stat().st_size > 1024:
                logger.info("Trailer indirildi (farklı format): %s", p.name)
                return p

        logger.warning("Trailer dosyası bulunamadı veya çok küçük.")
        return None

    except Exception as exc:
        logger.error("Trailer indirme başarısız: %s", exc)
        return None
