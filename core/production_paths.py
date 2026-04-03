"""Tarih + konu başlığına göre üretim klasörü; yayın (publish) bu modülde yok."""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from core.exceptions import ConfigError

logger = logging.getLogger(__name__)


def slugify_topic(name: str, max_len: int = 48) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-") or "topic"
    return s[:max_len].rstrip("-")


def production_run_dir(artifacts_root: Path, topic_name: str, when: datetime | None = None) -> Path:
    when = when or datetime.now(timezone.utc)
    stamp = when.strftime("%Y-%m-%d_%H%M%S")
    slug = slugify_topic(topic_name)
    return (artifacts_root / "productions" / f"{stamp}__{slug}").resolve()


def read_last_run_dir(artifacts_root: Path) -> Path | None:
    """productions/_last_run.txt içindeki üretim klasörü (varsa)."""
    p = artifacts_root / "productions" / "_last_run.txt"
    if not p.is_file():
        return None
    line = (p.read_text(encoding="utf-8").strip().splitlines() or [""])[0].strip()
    if not line:
        return None
    path = Path(line)
    return path.resolve() if path.is_dir() else None


def write_last_run_pointer(artifacts_root: Path, run_dir: Path) -> None:
    productions = artifacts_root / "productions"
    productions.mkdir(parents=True, exist_ok=True)
    ptr = productions / "_last_run.txt"
    ptr.write_text(str(run_dir.resolve()) + "\n", encoding="utf-8")
    logger.info("Son üretim klasörü kaydı: %s", ptr)


def find_latest_final_video(artifacts_root: Path) -> Path | None:
    productions = artifacts_root / "productions"
    if productions.is_dir():
        candidates = [p for p in productions.glob("*/video/final.mp4") if p.is_file()]
        if candidates:
            return max(candidates, key=lambda p: p.stat().st_mtime)
    legacy = artifacts_root / "video" / "final.mp4"
    return legacy if legacy.is_file() else None


def resolve_video_for_publish(artifacts_root: Path) -> Path:
    v = find_latest_final_video(artifacts_root)
    if v is None:
        raise ConfigError(
            "Yayın için video yok: önce üretim çalıştırın veya "
            "output/productions/.../video/final.mp4 veya output/video/final.mp4 oluşturun."
        )
    return v
