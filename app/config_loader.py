from pathlib import Path
from typing import Any

import yaml

from core.exceptions import ConfigError
from core.models import TopicConfig


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ConfigError(f"Config must be a mapping: {path}")
    return data


def load_topic_config(path: Path, topic_override: str | None = None) -> TopicConfig:
    raw = load_yaml(path)
    tc = TopicConfig.model_validate(raw)
    if topic_override is not None:
        tc = tc.model_copy(update={"topic_name": topic_override})
    return tc


def load_styles(path: Path) -> dict[str, Any]:
    return load_yaml(path)
