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
        Settings(watchtower_env="test"),
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
        Settings(watchtower_env="test"),
        repository,
        StaticQueryExecutor([[row], root, [row]]),
        agents=StubAgents(),
    )
    await runtime.initialize()
    assert len(await runtime.tick_if_due(force=True)) == 1
    assert await runtime.tick_if_due(force=True) == []
    assert len(repository.list_incidents()) == 1
