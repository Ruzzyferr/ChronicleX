#!/usr/bin/env python3
"""Docker Postgres hazır olana kadar bekle (SQLAlchemy ile SELECT 1)."""

from __future__ import annotations

import os
import sys
import time

from sqlalchemy import create_engine, text


def default_url() -> str:
    return (
        os.environ.get("CHRONICLE_TEST_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or "postgresql+psycopg2://chroniclex:chroniclex@127.0.0.1:5433/chroniclex"
    )


def main() -> int:
    url = default_url().strip()
    if not url:
        print("DATABASE_URL veya CHRONICLE_TEST_DATABASE_URL gerekli.", file=sys.stderr)
        return 1
    max_wait = int(os.environ.get("CHRONICLE_PG_WAIT_SEC", "90"))
    interval = 1.0
    deadline = time.monotonic() + max_wait
    last_err: str | None = None
    print(f"Waiting for PostgreSQL ({url.split('@')[-1] if '@' in url else url})...")
    while time.monotonic() < deadline:
        try:
            eng = create_engine(url, pool_pre_ping=True)
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            eng.dispose()
            print("PostgreSQL is ready.")
            return 0
        except Exception as e:
            last_err = str(e)
            time.sleep(interval)
    print(f"Timeout. Last error: {last_err}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
