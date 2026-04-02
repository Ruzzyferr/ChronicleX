from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class PublishMetadata:
    """Tek video için üç platformda paylaşılacak ortak metinler."""

    title: str
    description: str
    tags: list[str] = field(default_factory=list)
    channel_topic: str = ""
    youtube_privacy: str = "private"
    youtube_category_id: str = "22"


@dataclass
class PublishResult:
    platform: str
    success: bool
    post_id: str | None = None
    message: str = ""
    dry_run: bool = False
    preview: dict[str, Any] | None = None


class VideoPublisher(Protocol):
    @property
    def platform_name(self) -> str: ...

    def validate_credentials(self) -> None:
        """Eksik credential için ConfigError veya ValueError."""
        ...

    def dry_run_preview(self, metadata: PublishMetadata, video_path: Path) -> dict[str, Any]:
        ...

    def publish(
        self,
        metadata: PublishMetadata,
        video_path: Path,
        *,
        dry_run: bool,
    ) -> PublishResult:
        ...
