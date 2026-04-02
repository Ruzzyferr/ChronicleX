from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx

from app.settings import Settings
from core.exceptions import ConfigError
from modules.publishers.base import PublishMetadata, PublishResult

logger = logging.getLogger(__name__)


class InstagramPublisher:
    platform_name = "instagram"

    def __init__(self, settings: Settings) -> None:
        self._s = settings

    def validate_credentials(self) -> None:
        if not (self._s.instagram_access_token or "").strip():
            raise ConfigError("INSTAGRAM_ACCESS_TOKEN eksik.")
        if not (self._s.instagram_account_id or "").strip():
            raise ConfigError("INSTAGRAM_ACCOUNT_ID (IG User ID) eksik.")

    def dry_run_preview(self, metadata: PublishMetadata, video_path: Path) -> dict:
        return {
            "platform": self.platform_name,
            "caption": metadata.description[:2200],
            "video_path": str(video_path.resolve()),
            "ig_user_id": (self._s.instagram_account_id or "")[:8] + "...",
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
        gv = (self._s.facebook_graph_version or "v21.0").strip()
        ver = gv if gv.startswith("v") else f"v{gv}"
        ig = self._s.instagram_account_id.strip()
        token = self._s.instagram_access_token.strip()
        caption = metadata.description[:2200]

        try:
            with httpx.Client(timeout=120.0) as client:
                r = client.post(
                    f"https://graph.facebook.com/{ver}/{ig}/media",
                    data={
                        "upload_type": "resumable",
                        "media_type": "REELS",
                        "caption": caption,
                        "access_token": token,
                    },
                )
                r.raise_for_status()
                j = r.json()
            container_id = j.get("id")
            if not container_id:
                return PublishResult(
                    platform=self.platform_name,
                    success=False,
                    message=f"IG container oluşmadı: {j}",
                )
            uri = j.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{ver}/{container_id}"
            file_size = video_path.stat().st_size
            raw = video_path.read_bytes()
            with httpx.Client(timeout=900.0) as client:
                ur = client.post(
                    uri,
                    content=raw,
                    headers={
                        "Authorization": f"OAuth {token}",
                        "offset": "0",
                        "file_size": str(file_size),
                    },
                )
                ur.raise_for_status()
            logger.info("Instagram rupload tamam container=%s", container_id)

            ready = False
            for i in range(120):
                time.sleep(2)
                with httpx.Client(timeout=60.0) as client:
                    st = client.get(
                        f"https://graph.facebook.com/{ver}/{container_id}",
                        params={
                            "fields": "status_code,status,id",
                            "access_token": token,
                        },
                    )
                    st.raise_for_status()
                    sj = st.json()
                code = (sj.get("status_code") or "").upper()
                logger.debug("IG status poll %s: %s", i, sj)
                if code in ("FINISHED", "PUBLISHED", "OK"):
                    ready = True
                    break
                if code in ("ERROR", "EXPIRED"):
                    return PublishResult(
                        platform=self.platform_name,
                        success=False,
                        message=f"IG işleme hatası: {sj}",
                    )
            if not ready:
                return PublishResult(
                    platform=self.platform_name,
                    success=False,
                    message="IG video işleme zaman aşımı.",
                )

            with httpx.Client(timeout=120.0) as client:
                pub = client.post(
                    f"https://graph.facebook.com/{ver}/{ig}/media_publish",
                    data={"creation_id": container_id, "access_token": token},
                )
                pub.raise_for_status()
                pj = pub.json()
            media_id = pj.get("id")
            logger.info("Instagram yayınlandı id=%s", media_id)
            return PublishResult(
                platform=self.platform_name,
                success=True,
                post_id=str(media_id) if media_id else container_id,
                message="published",
            )
        except httpx.HTTPStatusError as e:
            logger.exception("Instagram HTTP")
            return PublishResult(
                platform=self.platform_name,
                success=False,
                message=f"HTTP {e.response.status_code}: {e.response.text[:400]}",
            )
        except Exception as e:
            logger.exception("Instagram publish")
            return PublishResult(platform=self.platform_name, success=False, message=str(e)[:500])
