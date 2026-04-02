from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from modules.publishers.base import PublishResult
from storage.models import PublishedVideoRow


def record_publish_run(
    session: Session,
    *,
    channel_topic: str,
    topic_id: int | None,
    video_path: str,
    results: list[PublishResult],
) -> PublishedVideoRow:
    row = PublishedVideoRow(
        channel_topic=channel_topic,
        topic_id=topic_id,
        video_path=video_path,
        publish_queue_status="published"
        if results and all(r.success for r in results)
        else ("partial" if any(r.success for r in results) else "failed"),
    )
    for r in results:
        if r.platform == "youtube":
            row.youtube_status = "published" if r.success else "failed"
            row.youtube_video_id = r.post_id
        elif r.platform == "tiktok":
            row.tiktok_status = "inbox" if r.success else "failed"
            row.tiktok_publish_id = r.post_id
        elif r.platform == "instagram":
            row.instagram_status = "published" if r.success else "failed"
            row.instagram_media_id = r.post_id
    row.published_at = datetime.now(timezone.utc)
    session.add(row)
    session.flush()
    return row
