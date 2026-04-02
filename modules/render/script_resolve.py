from __future__ import annotations

from pathlib import Path

from app.settings import Settings
from core.exceptions import ConfigError
from core.models import RunContext


def resolve_script_text(ctx: RunContext, output_base: Path, settings: Settings) -> str:
    """Narration metni: önce script dosyası, yoksa DB'de ready_for_script konusu."""
    script_file = output_base / "scripts" / "script.txt"
    if script_file.is_file():
        raw = script_file.read_text(encoding="utf-8")
        lines: list[str] = []
        for ln in raw.splitlines():
            s = ln.strip()
            if not s or s.startswith("#"):
                continue
            lines.append(ln.rstrip())
        body = "\n".join(lines).strip()
        if body:
            return body

    url = (settings.database_url or "").strip()
    if url:
        from storage.db import session_scope
        from storage.repositories.topics import get_ready_topic

        with session_scope(url) as session:
            row = get_ready_topic(session, ctx.effective_topic_name)
            if row is not None:
                parts = [row.title]
                if (row.summary or "").strip():
                    parts.append(row.summary.strip())
                return "\n\n".join(parts)

    raise ConfigError(
        "Render için metin gerekli: output/scripts/script.txt yazın (# ile yorum) veya "
        "DATABASE_URL ile bu kanal için ready_for_script olan bir topic oluşturun."
    )
