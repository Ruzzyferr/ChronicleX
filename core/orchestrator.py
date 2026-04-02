from __future__ import annotations

import logging
from pathlib import Path

from app.settings import Settings
from core.enums import PipelinePhase
from core.exceptions import ConfigError
from core.models import PhaseResult, RunContext

logger = logging.getLogger(__name__)

OUTPUT_SUBDIRS = (
    "logs",
    "scripts",
    "audio",
    "images",
    "subtitles",
    "video",
)


def ensure_directories(project_root: Path, output_base: Path) -> None:
    output_base.mkdir(parents=True, exist_ok=True)
    for name in OUTPUT_SUBDIRS:
        (output_base / name).mkdir(parents=True, exist_ok=True)
    (project_root / "data").mkdir(parents=True, exist_ok=True)
    (project_root / "temp").mkdir(parents=True, exist_ok=True)


def _should_run_phase(ctx: RunContext, phase: PipelinePhase) -> bool:
    if ctx.only_discovery:
        return phase == PipelinePhase.DISCOVERY
    if ctx.only_script:
        return phase == PipelinePhase.SCRIPTING
    if ctx.only_render:
        return phase == PipelinePhase.RENDER
    if ctx.only_publish:
        return phase == PipelinePhase.PUBLISH
    if phase == PipelinePhase.PUBLISH and not ctx.publish:
        return False
    return True


def _simulate_discovery(ctx: RunContext, output_base: Path) -> PhaseResult:
    paths: list[str] = []
    if ctx.dry_run:
        paths.append(str(output_base / "logs" / "discovery_dry_run.log"))
    logger.info("Discovery: %s candidates would be generated (Faz 2).", "10-50" if ctx.dry_run else "n/a")
    return PhaseResult(phase=PipelinePhase.DISCOVERY.value, dry_run=ctx.dry_run, outputs=paths)


def _run_discovery_live(settings: Settings, ctx: RunContext) -> PhaseResult:
    url = (settings.database_url or "").strip()
    if not url:
        raise ConfigError(
            "DATABASE_URL is not set. Use PostgreSQL, e.g. "
            "postgresql+psycopg2://user:pass@localhost:5432/chroniclex"
        )
    key = (settings.openai_api_key or "").strip()
    if not key:
        raise ConfigError("OPENAI_API_KEY is required for live discovery (or use --dry-run).")

    from storage.db import ensure_schema, session_scope

    if settings.auto_create_db_schema:
        ensure_schema(url)

    from modules.topic_discovery.adapters.openai_discovery import OpenAIDiscoveryAdapter
    from modules.topic_discovery.service import run_discovery_pipeline

    adapter = OpenAIDiscoveryAdapter(api_key=key, model=settings.openai_model)
    with session_scope(url) as session:
        detail = run_discovery_pipeline(session, settings, ctx.topic, adapter)

    outputs: list[str] = []
    tid = detail.get("chosen_topic_id")
    if tid is not None:
        outputs.append(f"topic_id={tid}")
    return PhaseResult(
        phase=PipelinePhase.DISCOVERY.value,
        dry_run=False,
        outputs=outputs,
        detail=detail,
    )


def _simulate_scripting(ctx: RunContext, output_base: Path) -> PhaseResult:
    script_path = output_base / "scripts" / "script.txt"
    paths = [str(script_path)]
    if ctx.dry_run:
        logger.info("[dry-run] Would write script to %s", script_path)
    else:
        topic = ctx.effective_topic_name
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(
            f"# Placeholder — Faz 3 render için en az 6 cümlelik anlatım; düzenleyebilirsiniz.\n\n"
            f"{topic} konusu, az bilinen ama kaynaklarıyla desteklenen bir tarihsel olayı anlatır.\n"
            f"Olayın geçtiği yer ve zaman dinleyiciyi sahnede hisseder.\n"
            f"Ana figürlerin seçimi ve kararları sonucu şekillenir.\n"
            f"Arşiv notları ve çağdaş tanıklıklar aynı hikâyeyi doğrular.\n"
            f"Sonuç, günümüzde hâlâ tartışılan bir miras bırakır.\n"
            f"Kısa biçimde güçlü bir açılış ve net bir kapanış hedeflenir.\n",
            encoding="utf-8",
        )
        logger.info("Wrote placeholder script: %s", script_path)
    return PhaseResult(phase=PipelinePhase.SCRIPTING.value, dry_run=ctx.dry_run, outputs=paths)


def _simulate_render(ctx: RunContext, output_base: Path) -> PhaseResult:
    paths = [
        str(output_base / "audio" / "voice.mp3"),
        str(output_base / "subtitles" / "subtitles.srt"),
        str(output_base / "video" / "final.mp4"),
    ]
    for p in paths:
        logger.info("[dry-run] Would produce media asset: %s", p)
    return PhaseResult(phase=PipelinePhase.RENDER.value, dry_run=True, outputs=paths)


def _run_render_live(settings: Settings, ctx: RunContext, output_base: Path) -> PhaseResult:
    from modules.render.media_pipeline import MediaPaths, run_media_pipeline
    from modules.render.script_resolve import resolve_script_text
    from storage.db import session_scope
    from storage.repositories.topics import get_ready_topic

    script = resolve_script_text(ctx, output_base, settings)
    paths = MediaPaths.from_output_base(ctx.project_root, output_base)
    topic_id: int | None = None
    url = (settings.database_url or "").strip()
    if url:
        with session_scope(url) as session:
            row = get_ready_topic(session, ctx.effective_topic_name)
            if row is not None:
                topic_id = row.id

    detail = run_media_pipeline(
        settings,
        script=script,
        paths=paths,
        topic_id=topic_id,
    )
    final = detail["manifest"]["final_video"]
    return PhaseResult(
        phase=PipelinePhase.RENDER.value,
        dry_run=False,
        outputs=[final, str(paths.video_dir / "manifest.json")],
        detail=detail,
    )


def _run_publish_phase(settings: Settings, ctx: RunContext, output_base: Path) -> PhaseResult:
    from dataclasses import asdict

    from modules.analytics.service import log_publish_snapshot
    from modules.publishers.coordinator import publish_to_all_enabled_platforms
    from storage.db import session_scope
    from storage.repositories import published_videos as pv_repo
    from storage.repositories.topics import get_ready_topic

    video_path = output_base / "video" / "final.mp4"
    results = publish_to_all_enabled_platforms(
        settings, ctx.topic, video_path, dry_run=ctx.dry_run
    )
    detail: dict = {
        "title": ctx.effective_topic_name,
        "results": [asdict(r) for r in results],
    }
    if not ctx.dry_run:
        log_publish_snapshot(results, ctx.effective_topic_name)
        url = (settings.database_url or "").strip()
        if url:
            with session_scope(url) as session:
                row = get_ready_topic(session, ctx.effective_topic_name)
                tid = row.id if row is not None else None
                pv_repo.record_publish_run(
                    session,
                    channel_topic=ctx.effective_topic_name,
                    topic_id=tid,
                    video_path=str(video_path.resolve()),
                    results=results,
                )
    outs = [str(video_path.resolve())]
    for r in results:
        if r.post_id:
            outs.append(f"{r.platform}_id={r.post_id}")
    return PhaseResult(
        phase=PipelinePhase.PUBLISH.value,
        dry_run=ctx.dry_run,
        outputs=outs,
        detail=detail,
    )


def run_pipeline(settings: Settings, ctx: RunContext) -> list[PhaseResult]:
    output_base = settings.resolved_output_dir()
    ensure_directories(ctx.project_root, output_base)

    log_file = output_base / "logs" / "app.log"
    _attach_file_handler(log_file)

    results: list[PhaseResult] = []
    phases_in_order = (
        PipelinePhase.DISCOVERY,
        PipelinePhase.SCRIPTING,
        PipelinePhase.RENDER,
        PipelinePhase.PUBLISH,
    )

    for phase in phases_in_order:
        if not _should_run_phase(ctx, phase):
            continue
        logger.info("Phase start: %s", phase.value)
        if phase == PipelinePhase.DISCOVERY:
            if ctx.dry_run:
                results.append(_simulate_discovery(ctx, output_base))
            else:
                results.append(_run_discovery_live(settings, ctx))
        elif phase == PipelinePhase.SCRIPTING:
            results.append(_simulate_scripting(ctx, output_base))
        elif phase == PipelinePhase.RENDER:
            if ctx.dry_run:
                results.append(_simulate_render(ctx, output_base))
            else:
                results.append(_run_render_live(settings, ctx, output_base))
        elif phase == PipelinePhase.PUBLISH:
            results.append(_run_publish_phase(settings, ctx, output_base))
        logger.info("Phase end: %s", phase.value)

    return results


_file_handler_added = False


def _attach_file_handler(log_path: Path) -> None:
    global _file_handler_added
    if _file_handler_added:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root = logging.getLogger()
    root.addHandler(fh)
    _file_handler_added = True
