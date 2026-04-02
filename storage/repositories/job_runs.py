from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from storage.models import JobRunRow


def start_job(session: Session, job_name: str, details: dict[str, Any]) -> JobRunRow:
    row = JobRunRow(job_name=job_name, status="running", details_json=details)
    session.add(row)
    session.flush()
    return row


def complete_job(
    session: Session, job_id: int, details: dict[str, Any] | None = None
) -> None:
    row = session.get(JobRunRow, job_id)
    if row is None:
        return
    row.status = "success"
    row.error_message = None
    if details is not None:
        row.details_json = {**dict(row.details_json or {}), **details}
    session.add(row)


def fail_job(session: Session, job_id: int, message: str) -> None:
    row = session.get(JobRunRow, job_id)
    if row is None:
        return
    row.status = "failed"
    row.error_message = message
    session.add(row)
