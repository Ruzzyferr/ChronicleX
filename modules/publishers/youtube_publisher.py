from __future__ import annotations

import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from app.settings import Settings
from core.exceptions import ConfigError
from modules.publishers.base import PublishMetadata, PublishResult

logger = logging.getLogger(__name__)

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"


class YouTubePublisher:
    platform_name = "youtube"

    def __init__(self, settings: Settings) -> None:
        self._s = settings

    def validate_credentials(self) -> None:
        if not (self._s.youtube_client_id or "").strip():
            raise ConfigError("YOUTUBE_CLIENT_ID eksik.")
        if not (self._s.youtube_client_secret or "").strip():
            raise ConfigError("YOUTUBE_CLIENT_SECRET eksik.")
        if not (self._s.youtube_refresh_token or "").strip():
            raise ConfigError("YOUTUBE_REFRESH_TOKEN eksik.")

    def _credentials(self) -> Credentials:
        self.validate_credentials()
        creds = Credentials(
            token=None,
            refresh_token=self._s.youtube_refresh_token.strip(),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self._s.youtube_client_id.strip(),
            client_secret=self._s.youtube_client_secret.strip(),
            scopes=[YOUTUBE_UPLOAD_SCOPE],
        )
        creds.refresh(Request())
        return creds

    def dry_run_preview(self, metadata: PublishMetadata, video_path: Path) -> dict:
        return {
            "platform": self.platform_name,
            "title": metadata.title,
            "privacy": metadata.youtube_privacy,
            "category_id": metadata.youtube_category_id,
            "tags": metadata.tags[:10],
            "video_path": str(video_path.resolve()),
            "size_bytes": video_path.stat().st_size if video_path.is_file() else None,
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
        if not video_path.is_file():
            return PublishResult(
                platform=self.platform_name,
                success=False,
                message="Video dosyası yok.",
            )
        try:
            creds = self._credentials()
            youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
            body = {
                "snippet": {
                    "title": metadata.title[:100],
                    "description": metadata.description[:5000],
                    "tags": metadata.tags[:30] if metadata.tags else [],
                    "categoryId": metadata.youtube_category_id,
                },
                "status": {
                    "privacyStatus": metadata.youtube_privacy,
                    "selfDeclaredMadeForKids": False,
                },
            }
            media = MediaFileUpload(
                str(video_path.resolve()),
                mimetype="video/mp4",
                resumable=True,
                chunksize=1024 * 1024 * 8,
            )
            logger.info("YouTube upload başlıyor: %s", metadata.title)
            request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    logger.debug("YouTube upload ilerleme: %s%%", int(status.progress() * 100))
            vid = response.get("id") if response else None
            logger.info("YouTube yüklendi id=%s", vid)
            return PublishResult(
                platform=self.platform_name,
                success=True,
                post_id=vid,
                message="ok",
            )
        except HttpError as e:
            msg = str(e)
            details = getattr(e, "error_details", None) or []
            if details and isinstance(details[0], dict):
                msg = details[0].get("message", msg)
            logger.exception("YouTube HttpError")
            return PublishResult(platform=self.platform_name, success=False, message=msg[:500])
        except Exception as e:
            logger.exception("YouTube upload hatası")
            return PublishResult(platform=self.platform_name, success=False, message=str(e)[:500])
