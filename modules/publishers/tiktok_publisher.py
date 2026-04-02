from __future__ import annotations

import logging
from pathlib import Path

import httpx

from app.settings import Settings
from core.exceptions import ConfigError
from modules.publishers.base import PublishMetadata, PublishResult

logger = logging.getLogger(__name__)

TIKTOK_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"


class TikTokPublisher:
    platform_name = "tiktok"

    def __init__(self, settings: Settings) -> None:
        self._s = settings

    def validate_credentials(self) -> None:
        if not (self._s.tiktok_access_token or "").strip():
            raise ConfigError("TIKTOK_ACCESS_TOKEN eksik (video.upload scope).")

    def dry_run_preview(self, metadata: PublishMetadata, video_path: Path) -> dict:
        return {
            "platform": self.platform_name,
            "title_hint": metadata.title,
            "caption_hint": metadata.description[:2200],
            "video_path": str(video_path.resolve()),
            "note": "TikTok inbox API: kullanıcı uygulamada düzenlemeyi tamamlar.",
        }

    def publish(
        self,
        metadata: PublishMetadata,
        video_path: Path,
        *,
        dry_run: bool,
    ) -> PublishResult:
        if dry_run:
            return PublishResult(
                platform=self.platform_name,
                success=True,
                dry_run=True,
                preview=self.dry_run_preview(metadata, video_path),
            )
        self.validate_credentials()
        if not video_path.is_file():
            return PublishResult(
                platform=self.platform_name,
                success=False,
                message="Video dosyası yok.",
            )
        token = self._s.tiktok_access_token.strip()
        size = video_path.stat().st_size
        chunk_size = size
        total_chunks = 1
        body = {
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunks,
            }
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
        }
        try:
            with httpx.Client(timeout=300.0) as client:
                r = client.post(TIKTOK_INIT_URL, headers=headers, json=body)
                r.raise_for_status()
                data = r.json()
            err = data.get("error") or {}
            if (err.get("code") or "").lower() != "ok":
                return PublishResult(
                    platform=self.platform_name,
                    success=False,
                    message=f"TikTok init: {err.get('message', data)}",
                )
            d = data.get("data") or {}
            upload_url = d.get("upload_url")
            publish_id = d.get("publish_id")
            if not upload_url:
                return PublishResult(
                    platform=self.platform_name,
                    success=False,
                    message="TikTok upload_url dönmedi.",
                )
            raw = video_path.read_bytes()
            last = len(raw) - 1
            put_headers = {
                "Content-Type": "video/mp4",
                "Content-Length": str(len(raw)),
                "Content-Range": f"bytes 0-{last}/{len(raw)}",
            }
            with httpx.Client(timeout=600.0) as client:
                pr = client.put(upload_url, content=raw, headers=put_headers)
                pr.raise_for_status()
            logger.info("TikTok yükleme tamam publish_id=%s", publish_id)
            return PublishResult(
                platform=self.platform_name,
                success=True,
                post_id=publish_id,
                message="uploaded_to_inbox",
            )
        except httpx.HTTPStatusError as e:
            logger.exception("TikTok HTTP")
            return PublishResult(
                platform=self.platform_name,
                success=False,
                message=f"HTTP {e.response.status_code}: {e.response.text[:400]}",
            )
        except Exception as e:
            logger.exception("TikTok upload")
            return PublishResult(platform=self.platform_name, success=False, message=str(e)[:500])
