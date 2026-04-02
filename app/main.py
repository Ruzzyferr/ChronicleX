from __future__ import annotations

import logging
import sys
from pathlib import Path

from app.cli import parse_args, run_with_args
from app.settings import clear_settings_cache, get_settings, project_root


def _run_init_db(settings) -> int:
    import logging

    log = logging.getLogger(__name__)
    url = (settings.database_url or "").strip()
    if not url:
        log.error("DATABASE_URL is not set. Use PostgreSQL, e.g. postgresql+psycopg2://user:pass@host:5432/dbname")
        return 1
    try:
        from storage.db import ensure_schema, ping_database, reset_engine_cache

        reset_engine_cache()
        ping_database(url)
        ensure_schema(url)
        log.info("Database connection OK and schema is up to date.")
    except Exception:
        log.exception("init-db failed")
        return 1
    return 0


def configure_logging() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError, AttributeError):
                pass
    root = logging.getLogger()
    if root.handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    clear_settings_cache()
    args = parse_args(argv)
    root = project_root()
    settings = get_settings()

    if args.init_db:
        return _run_init_db(settings)

    dry_run = args.dry_run or settings.dry_run
    try:
        run_with_args(args, settings=settings, project_root=root, dry_run=dry_run)
    except Exception:
        logging.exception("Run failed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
