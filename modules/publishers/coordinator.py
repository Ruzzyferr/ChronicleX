from __future__ import annotations

import logging
from pathlib import Path

from app.settings import Settings
from core.exceptions import ConfigError
from core.models import TopicConfig
from modules.publishers.base import PublishResult, VideoPublisher
from modules.publishers.copy_builder import build_publish_metadata
from modules.publishers.instagram_publisher import InstagramPublisher
from modules.publishers.tiktok_publisher import TikTokPublisher
from modules.publishers.youtube_publisher import YouTubePublisher

logger = logging.getLogger(__name__)


def _build_publishers(settings: Settings, topic: TopicConfig) -> list[VideoPublisher]:
    pub = topic.publishing
    out: list[VideoPublisher] = []
    if pub.youtube_enabled:
        out.append(YouTubePublisher(settings))
    if pub.tiktok_enabled:
        out.append(TikTokPublisher(settings))
    if pub.instagram_enabled:
        out.append(InstagramPublisher(settings))
    return out


def publish_to_all_enabled_platforms(
    settings: Settings,
    topic: TopicConfig,
    video_path: Path,
    *,
    dry_run: bool,
) -> list[PublishResult]:
    """Aynı video + aynı başlık/açıklama ile config’te açık tüm platformlara gönderir."""
    if not video_path.is_file():
        if dry_run:
            logger.warning("Video dosyası yok (%s); dry-run yalnızca payload önizlemesi.", video_path)
        else:
            raise FileNotFoundError(f"Video bulunamadı: {video_path}")
    metadata = build_publish_metadata(topic)
    publishers = _build_publishers(settings, topic)
    if not publishers:
        raise ConfigError("Hiçbir platform açık değil (topic.yaml publishing).")
    results: list[PublishResult] = []
    for p in publishers:
        name = p.platform_name
        try:
            if not dry_run:
                p.validate_credentials()
        except ConfigError as e:
            logger.warning("%s atlandı: %s", name, e)
            results.append(
                PublishResult(platform=name, success=False, message=str(e), dry_run=False)
            )
            continue
        except Exception as e:
            logger.warning("%s credential kontrolü hatası: %s", name, e)
            results.append(
                PublishResult(platform=name, success=False, message=str(e), dry_run=False)
            )
            continue
        logger.info("Publish başlıyor: %s dry_run=%s", name, dry_run)
        res = p.publish(metadata, video_path, dry_run=dry_run)
        results.append(res)
        if res.success:
            logger.info("%s tamam post_id=%s", name, res.post_id)
        else:
            logger.error("%s başarısız: %s", name, res.message)
    return results
