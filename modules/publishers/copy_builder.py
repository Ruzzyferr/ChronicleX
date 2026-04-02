from __future__ import annotations

from core.models import TopicConfig


def build_publish_metadata(topic: TopicConfig) -> "PublishMetadata":
    from modules.publishers.base import PublishMetadata

    pub = topic.publishing
    desc_parts = []
    if (pub.description_prefix or "").strip():
        desc_parts.append(pub.description_prefix.strip())
    if (topic.tone or "").strip():
        desc_parts.append(topic.tone.strip())
    desc_parts.append(topic.topic_name)
    description = "\n\n".join(desc_parts)[:5000]
    title = topic.topic_name.strip()[:100]
    if not title:
        title = topic.topic_name[:100]
    return PublishMetadata(
        title=title,
        description=description,
        tags=list(pub.tags)[:30],
        channel_topic=topic.topic_name,
        youtube_privacy=pub.youtube_privacy,
        youtube_category_id=pub.youtube_category_id,
    )
