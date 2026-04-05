from __future__ import annotations

import logging
from pathlib import Path

from app.settings import Settings
from core.enums import PipelinePhase
from core.exceptions import ConfigError
from core.models import PhaseResult, RunContext
from core.production_paths import (
    production_run_dir,
    read_last_run_dir,
    resolve_video_for_publish,
    write_last_run_pointer,
)

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
    if (
        phase == PipelinePhase.DISCOVERY
        and ctx.topic_cli_override
        and not ctx.only_discovery
    ):
        logger.info(
            "Discovery atlandı: --topic ile sabit başlık verildi (novelty/DB adayı gerekmez)."
        )
        return False
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


def _simulate_scripting(settings: Settings, ctx: RunContext, output_base: Path) -> PhaseResult:
    script_path = output_base / "scripts" / "script.txt"
    paths = [str(script_path)]
    if ctx.dry_run:
        logger.info("[dry-run] Would write script to %s", script_path)
    else:
        key = (settings.openai_api_key or "").strip()
        if key:
            if ctx.psych:
                from modules.scripting.psych_narration import (
                    interactive_topic_select,
                    write_psych_script_and_scenes,
                )

                # Interaktif konu seçimi (--topic verilmediyse)
                if not ctx.topic.topic_name.strip():
                    selected_topic = interactive_topic_select(api_key=key, model=settings.openai_model)
                    ctx.topic = ctx.topic.model_copy(update={"topic_name": selected_topic})

                write_psych_script_and_scenes(
                    topic=ctx.topic,
                    output_base=output_base,
                    api_key=key,
                    model=settings.openai_model,
                )
                paths.append(str(output_base / "scripts" / "topic_scenes.json"))
                logger.info("Psikoloji / Dark Psychology senaryosu yazıldı.")
            elif ctx.vaka_url:
                from modules.scripting.vaka_narration import write_vaka_script_and_scenes

                write_vaka_script_and_scenes(
                    topic=ctx.topic,
                    output_base=output_base,
                    api_key=key,
                    model=settings.openai_model,
                    vaka_url=ctx.vaka_url,
                )
                paths.append(str(output_base / "scripts" / "topic_scenes.json"))
                logger.info("Vaka senaryosu (dedektif tarzı) yazıldı.")
            elif ctx.search_movie:
                from modules.scripting.movie_narration import write_movie_script_and_scenes

                write_movie_script_and_scenes(
                    topic=ctx.topic,
                    output_base=output_base,
                    api_key=key,
                    model=settings.openai_model,
                )
                paths.append(str(output_base / "scripts" / "topic_scenes.json"))
                logger.info("Film özeti (spoiler'sız) script ve sahne planı yazıldı.")
            else:
                from modules.scripting.topic_narration import write_topic_script_and_scenes

                write_topic_script_and_scenes(
                    topic=ctx.topic,
                    output_base=output_base,
                    api_key=key,
                    model=settings.openai_model,
                )
                paths.append(str(output_base / "scripts" / "topic_scenes.json"))
                logger.info("OpenAI ile konu anlatımı ve sahne görselleri planı yazıldı.")
        else:
            topic = ctx.effective_topic_name
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text(
                f"# Placeholder — OPENAI_API_KEY yok. Metni elle yazın veya .env ekleyin.\n\n"
                f"{topic} konusu, az bilinen ama kaynaklarıyla desteklenen bir tarihsel olayı anlatır.\n"
                f"Olayın geçtiği yer ve zaman dinleyiciyi sahnede hisseder.\n"
                f"Ana figürlerin seçimi ve kararları sonucu şekillenir.\n"
                f"Arşiv notları ve çağdaş tanıklıklar aynı hikâyeyi doğrular.\n"
                f"Sonuç, günümüzde hâlâ tartışılan bir miras bırakır.\n"
                f"Kısa biçimde güçlü bir açılış ve net bir kapanış hedeflenir.\n",
                encoding="utf-8",
            )
            logger.warning("OPENAI_API_KEY yok; placeholder script yazıldı: %s", script_path)
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
        topic_name=ctx.effective_topic_name,
        with_pics=ctx.with_pics,
        search_movie=ctx.search_movie,
        resume=ctx.resume_render,
        use_ambient=ctx.search_movie or bool(ctx.vaka_url),
    )
    final = detail["manifest"]["final_video"]
    return PhaseResult(
        phase=PipelinePhase.RENDER.value,
        dry_run=False,
        outputs=[final, str(paths.video_dir / "manifest.json")],
        detail=detail,
    )


def _run_publish_phase(
    settings: Settings,
    ctx: RunContext,
    output_base: Path,
    *,
    video_path: Path | None = None,
) -> PhaseResult:
    from dataclasses import asdict

    from modules.analytics.service import log_publish_snapshot
    from modules.publishers.coordinator import publish_to_all_enabled_platforms
    from storage.db import session_scope
    from storage.repositories import published_videos as pv_repo
    from storage.repositories.topics import get_ready_topic

    if video_path is None:
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


def _resolve_output_base(settings: Settings, ctx: RunContext) -> tuple[Path, Path, Path | None]:
    """(artifacts_root, phase_output_base, publish_video_path_override)."""
    artifacts_root = settings.resolved_output_dir()
    publish_video: Path | None = None

    if ctx.only_publish:
        publish_video = resolve_video_for_publish(artifacts_root)
        return artifacts_root, artifacts_root, publish_video

    if (
        ctx.only_render
        and not ctx.dry_run
        and ctx.resume_render
        and settings.use_production_subfolders
    ):
        if ctx.from_output is not None:
            run_dir = ctx.from_output.resolve()
        else:
            run_dir = read_last_run_dir(artifacts_root)
        if run_dir is None or not run_dir.is_dir():
            raise ConfigError(
                "--resume-render: üretim klasörü yok. "
                "Önce tam pipeline çalıştırın veya --from-output output/productions/<klasör> verin."
            )
        return artifacts_root, run_dir, None

    if ctx.dry_run or not settings.use_production_subfolders:
        return artifacts_root, artifacts_root, None

    run_dir = production_run_dir(artifacts_root, ctx.effective_topic_name)
    return artifacts_root, run_dir, None


def run_pipeline(settings: Settings, ctx: RunContext) -> list[PhaseResult]:
    # Rescue modu: normal pipeline atlanır, doğrudan rescue pipeline çağrılır
    if ctx.rescue_url:
        return _run_rescue_mode(settings, ctx)

    artifacts_root, output_base, publish_video_override = _resolve_output_base(settings, ctx)
    ensure_directories(ctx.project_root, output_base)

    log_file = output_base / "logs" / "app.log"
    _attach_file_handler(log_file)

    if output_base != artifacts_root and not ctx.only_publish:
        logger.info("Üretim klasörü: %s", output_base)
    elif ctx.only_publish and publish_video_override:
        logger.info("Yayın videosu: %s", publish_video_override)

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
            results.append(_simulate_scripting(settings, ctx, output_base))
        elif phase == PipelinePhase.RENDER:
            if ctx.dry_run:
                results.append(_simulate_render(ctx, output_base))
            else:
                results.append(_run_render_live(settings, ctx, output_base))
                if settings.use_production_subfolders and output_base != artifacts_root:
                    write_last_run_pointer(artifacts_root, output_base)
                    logger.info("Video ve varlıklar: %s", output_base / "video")
        elif phase == PipelinePhase.PUBLISH:
            results.append(
                _run_publish_phase(
                    settings,
                    ctx,
                    output_base,
                    video_path=publish_video_override,
                )
            )
        logger.info("Phase end: %s", phase.value)

    return results


def _run_rescue_mode(settings: Settings, ctx: RunContext) -> list[PhaseResult]:
    """Rescue modu: YouTube → indir → edit → overlay → thumbnail."""
    from modules.rescue.pipeline import run_rescue_pipeline

    artifacts_root = settings.resolved_output_dir()
    if settings.use_production_subfolders and not ctx.dry_run:
        output_base = production_run_dir(artifacts_root, ctx.effective_topic_name)
    else:
        output_base = artifacts_root

    ensure_directories(ctx.project_root, output_base)
    log_file = output_base / "logs" / "app.log"
    _attach_file_handler(log_file)
    logger.info("Rescue modu başlatılıyor: %s", ctx.rescue_url)

    if ctx.dry_run:
        logger.info("[dry-run] Rescue pipeline simülasyonu.")
        return [PhaseResult(phase="rescue", dry_run=True, outputs=[])]

    detail = run_rescue_pipeline(
        settings=settings,
        url=ctx.rescue_url,
        output_base=output_base,
        start_sec=ctx.rescue_start,
        end_sec=ctx.rescue_end,
    )

    if settings.use_production_subfolders and output_base != artifacts_root:
        write_last_run_pointer(artifacts_root, output_base)

    return [PhaseResult(
        phase="rescue",
        dry_run=False,
        outputs=[detail.get("final_video", ""), detail.get("thumbnail", "")],
        detail=detail,
    )]


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
