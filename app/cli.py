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
        description="ChronicleX: konu başlığı → keşif / script / video üretimi. "
        "Yayın isteğe bağlı (--publish / --only-publish; varsayılan kapalı).",
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
        help="[Raf — isteğe bağlı] Pipeline sonunda yayın (YouTube/TikTok/IG); normal akışta kullanılmaz",
    )
    p.add_argument(
        "--ship",
        action="store_true",
        help="--publish ile aynı (kısayol); normal akışta kullanılmaz",
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
        "--resume-render",
        action="store_true",
        help="Kaldığı yerden: son üretim klasöründe (veya --from-output) var olan sahne/görsel/sesi atla",
    )
    p.add_argument(
        "--withpics",
        action="store_true",
        help="Gameplay modunda Lexica'dan konu görselleri overlay ekle",
    )
    p.add_argument(
        "--searchmovie",
        action="store_true",
        help="Film modu: YouTube'dan trailer indir, kesitlerden video oluştur, spoiler'sız film özeti anlat",
    )
    p.add_argument(
        "--from-output",
        type=str,
        default=None,
        help="Üretim kökü (ör. output/productions/2026-04-02_...); --resume-render ile birlikte",
    )
    p.add_argument(
        "--only-publish",
        action="store_true",
        help="[Raf] Sadece yayın: son üretilen video (productions veya output/video)",
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

    if args.resume_render and not args.only_render:
        raise ConfigError("--resume-render yalnızca --only-render ile kullanılır.")

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

    from_output_path: Path | None = None
    if args.from_output:
        from_output_path = _resolve_path(project_root, args.from_output)

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
        with_pics=args.withpics,
        search_movie=args.searchmovie,
        resume_render=args.resume_render,
        from_output=from_output_path,
        topic_cli_override=bool(args.topic),
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
