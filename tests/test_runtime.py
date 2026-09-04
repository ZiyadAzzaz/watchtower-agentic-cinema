from datetime import UTC, datetime

import pytest

from watchtower.agents import ActionDraft, AgentPipelineResult
from watchtower.config import Settings
from watchtower.mcp_client import StaticQueryExecutor
from watchtower.models import AgentTraceStep, AnomalyInjectionRequest, AnomalyKind
from watchtower.repository import MemoryRepository
from watchtower.runtime import WatchtowerRuntime


class StubAgents:
    async def run(self, anomaly, root_cause, impact) -> AgentPipelineResult:
        now = datetime.now(UTC)
        return AgentPipelineResult(
            draft=ActionDraft(
                executive_brief=(
                    "A verified delivery anomaly is affecting the fictional title in one region. "
                    "The quantified viewer and revenue impact has been calculated from audited "
                    "inputs."
                ),
                recommended_action=(
                    "Route a small canary away from the affected node, pending human approval."
                ),
            ),
            trace=[
                AgentTraceStep(
                    agent="Detector",
                    summary="Validated through MCP.",
                    started_at=now,
                    completed_at=now,
                    duration_ms=1,
                )
            ],
            used_gemini=True,
        )


@pytest.mark.asyncio
async def test_full_runtime_creates_pending_human_decision() -> None:
    detection_rows = [
        {
            "title_id": "aurora-drift",
            "region": "MENA",
            "current_views": 95,
            "baseline_views": 100,
            "current_buffer_rate": 0.28,
            "baseline_buffer_rate": 0.02,
            "current_ad_error_rate": 0.01,
            "baseline_ad_error_rate": 0.01,
            "current_starts": 600,
            "current_completions": 410,
        }
    ]
    root_rows = [
        {
            "cdn_node": "me-edge-02",
            "views": 90,
            "buffer_rate": 0.31,
            "ad_error_rate": 0.01,
            "signal_tags": ["buffer_spike"],
        }
    ]
    repository = MemoryRepository()
    runtime = WatchtowerRuntime(
        Settings(watchtower_env="test", _env_file=None),
        repository,
        StaticQueryExecutor([detection_rows, root_rows]),
        agents=StubAgents(),
    )
    await runtime.initialize()
    runtime.inject(
        AnomalyInjectionRequest(
            kind=AnomalyKind.BUFFER_SPIKE,
            title_id="aurora-drift",
            region="MENA",
        )
    )
    incidents = await runtime.tick_if_due(force=True)
    assert len(incidents) == 1
    assert incidents[0].status.value == "pending_approval"
    assert incidents[0].root_cause.primary_value == "me-edge-02"
    assert incidents[0].impact.estimated_revenue_loss_usd > 0
    assert runtime.used_gemini


@pytest.mark.asyncio
async def test_runtime_suppresses_duplicate_open_incident() -> None:
    row = {
        "title_id": "aurora-drift",
        "region": "MENA",
        "current_views": 20,
        "baseline_views": 100,
        "current_buffer_rate": 0.02,
        "baseline_buffer_rate": 0.02,
        "current_ad_error_rate": 0.01,
        "baseline_ad_error_rate": 0.01,
        "current_starts": 600,
        "current_completions": 300,
    }
    root = [{"cdn_node": "me-edge-01", "views": 20}]
    repository = MemoryRepository()
    runtime = WatchtowerRuntime(
        Settings(watchtower_env="test", _env_file=None),
        repository,
        StaticQueryExecutor([[row], root, [row]]),
        agents=StubAgents(),
    )
    await runtime.initialize()
    assert len(await runtime.tick_if_due(force=True)) == 1
    assert await runtime.tick_if_due(force=True) == []
    assert len(repository.list_incidents()) == 1


@pytest.mark.asyncio
async def test_stale_history_is_reseeded() -> None:
    """Rows stored days ago leave the detection windows empty."""
    from datetime import timedelta

    repository = MemoryRepository()
    runtime = WatchtowerRuntime(
        Settings(watchtower_env="test", _env_file=None),
        repository,
        StaticQueryExecutor([]),
        agents=StubAgents(),
    )
    stale = datetime.now(UTC) - timedelta(days=3)
    repository.insert_events(runtime.generator.generate_cycle(stale) * 40)
    assert repository.event_count() >= 1200
    assert repository.recent_event_count(67) == 0

    assert await runtime.ensure_baseline_history() is True
    assert repository.recent_event_count(67) >= 1200
    # A fresh baseline must not be re-seeded on the next call.
    assert await runtime.ensure_baseline_history() is False


def test_clickhouse_timestamps_are_marked_utc() -> None:
    """A naive timestamp is read as local time by the browser."""
    from watchtower.runtime import _as_utc_iso

    assert _as_utc_iso("2026-09-04 10:13:56.805000") == "2026-09-04T10:13:56.805000Z"
    assert _as_utc_iso("2026-09-04 09:44:00") == "2026-09-04T09:44:00Z"
    # Already-marked values and non-strings pass through untouched.
    assert _as_utc_iso("2026-09-04T09:44:00Z") == "2026-09-04T09:44:00Z"
    assert _as_utc_iso("2026-09-04T09:44:00+00:00") == "2026-09-04T09:44:00+00:00"
    assert _as_utc_iso(None) is None
    assert _as_utc_iso(datetime(2026, 9, 4, 9, 44, tzinfo=UTC)) == "2026-09-04T09:44:00+00:00"


@pytest.mark.asyncio
async def test_dashboard_marks_timestamps_utc() -> None:
    runtime = WatchtowerRuntime(
        Settings(watchtower_env="test", _env_file=None),
        MemoryRepository(),
        StaticQueryExecutor(
            [
                [],  # the detection scan dashboard() runs first
                [{"event_count": 1, "last_event_at": "2026-09-04 10:13:56"}],
                [{"minute": "2026-09-04 09:44:00", "views": 10}],
            ]
        ),
        agents=StubAgents(),
    )
    payload = await runtime.dashboard()
    assert payload["summary"]["last_event_at"] == "2026-09-04T10:13:56Z"
    assert payload["timeseries"][0]["minute"] == "2026-09-04T09:44:00Z"
