from __future__ import annotations

import argparse
import logging
from pathlib import Path

from app.config_loader import load_styles, load_topic_config
from app.settings import Settings
from core.exceptions import ConfigError
from core.models import RunContext, TopicConfig
from core.orchestrator import run_pipeline

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Channel automation: topic → script → media → publish (CLI).",
    )
    p.add_argument(
        "--topic",
        type=str,
        default=None,
        help="Override topic_name from config/topic.yaml",
    )
    p.add_argument(
        "--config",
        type=str,
        default="config/topic.yaml",
        help="Path to topic YAML (relative to project root unless absolute)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate pipeline; no external API calls or uploads",
    )
    p.add_argument(
        "--publish",
        action="store_true",
        help="Pipeline sonunda yayın adımını çalıştır (üç platform, topic başlığı ortak)",
    )
    p.add_argument(
        "--ship",
        action="store_true",
        help="--publish ile aynı: üretim + üç platforma gönderim (dry-run ile birlikte önizleme)",
    )
    p.add_argument(
        "--only-discovery",
        action="store_true",
        help="Run only topic discovery phase (Faz 2 will implement)",
    )
    p.add_argument(
        "--only-script",
        action="store_true",
        help="Run only scripting phase",
    )
    p.add_argument(
        "--only-render",
        action="store_true",
        help="Run only render/media phase (Faz 3)",
    )
    p.add_argument(
        "--only-publish",
        action="store_true",
        help="Run only publish phase (Faz 4)",
    )
    p.add_argument(
        "--init-db",
        action="store_true",
        help="Create database tables from models (PostgreSQL) and exit",
    )
    return p.parse_args(argv)


def _resolve_path(project_root: Path, path_str: str) -> Path:
    p = Path(path_str)
    return p if p.is_absolute() else (project_root / p).resolve()


def run_with_args(
    args: argparse.Namespace,
    *,
    settings: Settings,
    project_root: Path,
    dry_run: bool,
) -> None:
    only_flags = (
        args.only_discovery,
        args.only_script,
        args.only_render,
        args.only_publish,
    )
    if sum(1 for f in only_flags if f) > 1:
        raise ConfigError("Use at most one of --only-discovery, --only-script, --only-render, --only-publish")

    config_path = _resolve_path(project_root, args.config)
    topic = load_topic_config(config_path)
    if args.topic:
        topic = topic.model_copy(update={"topic_name": args.topic})

    styles_path = project_root / "config" / "styles.yaml"
    if styles_path.is_file():
        styles = load_styles(styles_path)
        logger.debug("Loaded styles keys: %s", list(styles.keys()))
    else:
        logger.warning("styles.yaml not found at %s", styles_path)

    ctx = RunContext(
        project_root=project_root,
        config_path=config_path,
        topic=topic,
        dry_run=dry_run,
        publish=bool(args.publish or args.ship),
        only_discovery=args.only_discovery,
        only_script=args.only_script,
        only_render=args.only_render,
        only_publish=args.only_publish,
    )

    logger.info("Application start project_root=%s", project_root)
    logger.info("Config file=%s", config_path)
    logger.info(
        "Active topic=%s dry_run=%s publish_flag=%s",
        ctx.effective_topic_name,
        dry_run,
        ctx.publish,
    )

    run_pipeline(settings, ctx)
    logger.info("Application finished")
