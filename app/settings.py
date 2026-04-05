from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    tts_api_key: str | None = Field(default=None, alias="TTS_API_KEY")
    elevenlabs_api_key: str | None = Field(default=None, alias="ELEVENLABS_API_KEY")
    image_api_key: str | None = Field(default=None, alias="IMAGE_API_KEY")

    youtube_client_id: str | None = Field(default=None, alias="YOUTUBE_CLIENT_ID")
    youtube_client_secret: str | None = Field(default=None, alias="YOUTUBE_CLIENT_SECRET")
    youtube_refresh_token: str | None = Field(default=None, alias="YOUTUBE_REFRESH_TOKEN")

    tiktok_client_key: str | None = Field(default=None, alias="TIKTOK_CLIENT_KEY")
    tiktok_client_secret: str | None = Field(default=None, alias="TIKTOK_CLIENT_SECRET")

    instagram_access_token: str | None = Field(default=None, alias="INSTAGRAM_ACCESS_TOKEN")
    instagram_account_id: str | None = Field(default=None, alias="INSTAGRAM_ACCOUNT_ID")
    facebook_graph_version: str = Field(default="v21.0", alias="FACEBOOK_GRAPH_VERSION")

    tiktok_access_token: str | None = Field(default=None, alias="TIKTOK_ACCESS_TOKEN")

    output_dir: Path | None = Field(default=None, alias="OUTPUT_DIR")
    # Gerçek üretimde output/productions/<tarih>__<konu>/ (dry-run ve only-publish hariç)
    use_production_subfolders: bool = Field(default=True, alias="OUTPUT_USE_PRODUCTION_SUBFOLDERS")
    database_url: str = Field(default="", alias="DATABASE_URL")
    auto_create_db_schema: bool = Field(default=True, alias="AUTO_CREATE_DB_SCHEMA")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    dalle_model: str = Field(default="dall-e-3", alias="DALLE_MODEL")
    dalle_size: str = Field(default="1024x1792", alias="DALLE_SIZE")
    elevenlabs_voice_id: str = Field(
        default="21m00Tcm4TlvDq8ikWAM",
        alias="ELEVENLABS_VOICE_ID",
    )
    elevenlabs_model_id: str = Field(
        default="eleven_multilingual_v2",
        alias="ELEVENLABS_MODEL_ID",
    )
    background_video_dir: str = Field(default="assets/backgrounds", alias="BACKGROUND_VIDEO_DIR")
    ambient_audio_dir: str = Field(default="assets/ambient", alias="AMBIENT_AUDIO_DIR")
    ffmpeg_path: str = Field(default="ffmpeg", alias="FFMPEG_PATH")
    ffprobe_path: str = Field(default="ffprobe", alias="FFPROBE_PATH")
    default_language: str = Field(default="tr", alias="DEFAULT_LANGUAGE")
    default_timezone: str = Field(default="Europe/Istanbul", alias="DEFAULT_TIMEZONE")
    dry_run: bool = Field(default=False, alias="DRY_RUN")

    @field_validator("output_dir", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if v == "":
            return None
        return v

    def resolved_output_dir(self) -> Path:
        base = self.output_dir if self.output_dir is not None else project_root() / "output"
        return base.resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
