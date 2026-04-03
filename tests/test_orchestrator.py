"""Tests for orchestrator phase selection logic."""

from __future__ import annotations

from pathlib import Path

from core.enums import PipelinePhase
from core.models import RunContext, TopicConfig
from core.orchestrator import _should_run_phase


def _ctx(**overrides) -> RunContext:
    defaults = dict(
        project_root=Path("."),
        config_path=Path("config/topic.yaml"),
        topic=TopicConfig(topic_name="test"),
        dry_run=True,
        publish=False,
        only_discovery=False,
        only_script=False,
        only_render=False,
        only_publish=False,
        topic_cli_override=False,
    )
    defaults.update(overrides)
    return RunContext(**defaults)


def test_default_runs_all_except_publish():
    ctx = _ctx()
    assert _should_run_phase(ctx, PipelinePhase.DISCOVERY) is True
    assert _should_run_phase(ctx, PipelinePhase.SCRIPTING) is True
    assert _should_run_phase(ctx, PipelinePhase.RENDER) is True
    assert _should_run_phase(ctx, PipelinePhase.PUBLISH) is False


def test_only_discovery():
    ctx = _ctx(only_discovery=True)
    assert _should_run_phase(ctx, PipelinePhase.DISCOVERY) is True
    assert _should_run_phase(ctx, PipelinePhase.SCRIPTING) is False
    assert _should_run_phase(ctx, PipelinePhase.RENDER) is False
    assert _should_run_phase(ctx, PipelinePhase.PUBLISH) is False


def test_only_script():
    ctx = _ctx(only_script=True)
    assert _should_run_phase(ctx, PipelinePhase.DISCOVERY) is False
    assert _should_run_phase(ctx, PipelinePhase.SCRIPTING) is True


def test_only_render():
    ctx = _ctx(only_render=True)
    assert _should_run_phase(ctx, PipelinePhase.DISCOVERY) is False
    assert _should_run_phase(ctx, PipelinePhase.RENDER) is True


def test_only_publish():
    ctx = _ctx(only_publish=True)
    assert _should_run_phase(ctx, PipelinePhase.DISCOVERY) is False
    assert _should_run_phase(ctx, PipelinePhase.PUBLISH) is True


def test_publish_flag_enables_publish():
    ctx = _ctx(publish=True)
    assert _should_run_phase(ctx, PipelinePhase.PUBLISH) is True
    assert _should_run_phase(ctx, PipelinePhase.DISCOVERY) is True


def test_cli_topic_skips_discovery_in_full_pipeline():
    ctx = _ctx(topic_cli_override=True)
    assert _should_run_phase(ctx, PipelinePhase.DISCOVERY) is False
    assert _should_run_phase(ctx, PipelinePhase.SCRIPTING) is True


def test_cli_topic_still_runs_discovery_when_only_discovery():
    ctx = _ctx(topic_cli_override=True, only_discovery=True)
    assert _should_run_phase(ctx, PipelinePhase.DISCOVERY) is True
    assert _should_run_phase(ctx, PipelinePhase.SCRIPTING) is False
