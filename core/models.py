from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ContentRules(BaseModel):
    must_be_real: bool = True
    avoid_repetition: bool = True
    minimum_shock_score: int = 8
    minimum_verification_score: int = 7
    min_sources: int = 2


class PublishingFlags(BaseModel):
    youtube_enabled: bool = True
    tiktok_enabled: bool = True
    instagram_enabled: bool = True
    youtube_privacy: str = "private"
    youtube_category_id: str = "22"
    tags: list[str] = Field(default_factory=list)
    description_prefix: str = ""


class TopicConfig(BaseModel):
    topic_name: str
    language: str = "tr"
    tone: str = ""
    video_duration_seconds: int = 45
    content_rules: ContentRules = Field(default_factory=ContentRules)
    publishing: PublishingFlags = Field(default_factory=PublishingFlags)


class RunContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    project_root: Path
    config_path: Path
    topic: TopicConfig
    dry_run: bool
    publish: bool
    only_discovery: bool
    only_script: bool
    only_render: bool
    only_publish: bool
    with_pics: bool = False
    search_movie: bool = False
    psych: bool = False
    resume_render: bool = False
    from_output: Path | None = None
    vaka_url: str | None = None
    rescue_url: str | None = None
    # True ise --topic ile başlık komut satırından verildi (tam pipeline’da keşif atlanır)
    topic_cli_override: bool = False

    @property
    def effective_topic_name(self) -> str:
        return self.topic.topic_name


class PhaseResult(BaseModel):
    phase: str
    dry_run: bool
    outputs: list[str] = Field(default_factory=list)
    detail: dict[str, Any] = Field(default_factory=dict)
