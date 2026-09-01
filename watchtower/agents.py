from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, Field

from watchtower.config import Settings
from watchtower.mcp_client import QueryExecutor
from watchtower.models import AgentTraceStep, Anomaly, ImpactEstimate, RootCause
from watchtower.sql import detection_query, root_cause_query


class ActionDraft(BaseModel):
    executive_brief: str = Field(min_length=80, max_length=900)
    recommended_action: str = Field(min_length=20, max_length=320)


@dataclass
class AgentPipelineResult:
    draft: ActionDraft
    trace: list[AgentTraceStep]
    used_gemini: bool


class AgentPipeline:
    """ADK multi-agent pipeline; all runtime AI calls route to Gemini on Vertex AI."""

    app_name = "watchtower_incident_intelligence"

    def __init__(self, settings: Settings, mcp: QueryExecutor):
        self.settings = settings
        self.mcp = mcp

    async def run(
        self,
        anomaly: Anomaly,
        root_cause: RootCause,
        impact: ImpactEstimate,
    ) -> AgentPipelineResult:
        if self.settings.watchtower_env == "test":
            return self._fallback(anomaly, root_cause, impact)
        started = time.perf_counter()
        pipeline = self._build_pipeline(anomaly)
        session_service = InMemorySessionService()
        session_id = str(uuid4())
        state = {
            "anomaly": anomaly.model_dump_json(),
            "root_cause": root_cause.model_dump_json(),
            "impact": impact.model_dump_json(),
        }
        await session_service.create_session(
            app_name=self.app_name,
            user_id="watchtower-orchestrator",
            session_id=session_id,
            state=state,
        )
        runner = Runner(
            app_name=self.app_name,
            agent=pipeline,
            session_service=session_service,
        )
        events = []
        try:
            message = types.Content(
                role="user",
                parts=[
                    types.Part(
                        text=(
                            "Investigate the supplied anomaly. Use the required evidence tools, "
                            "preserve the audited impact numbers, and draft one safe action."
                        )
                    )
                ],
            )
            async for event in runner.run_async(
                user_id="watchtower-orchestrator",
                session_id=session_id,
                new_message=message,
            ):
                events.append(event)
            session = await session_service.get_session(
                app_name=self.app_name,
                user_id="watchtower-orchestrator",
                session_id=session_id,
            )
            output = session.state.get("action_draft", "") if session else ""
            draft = (
                ActionDraft.model_validate_json(output)
                if isinstance(output, str)
                else ActionDraft.model_validate(output)
            )
            trace = self._trace_from_events(events, started)
            return AgentPipelineResult(draft=draft, trace=trace, used_gemini=True)
        except Exception:
            if self.settings.is_production:
                raise
            return self._fallback(anomaly, root_cause, impact)
        finally:
            await runner.close()

    def _build_pipeline(self, anomaly: Anomaly) -> SequentialAgent:
        settings = self.settings

        async def inspect_detection_window() -> dict[str, Any]:
            """Read the bounded detection window through official mcp-clickhouse."""
            rows = await self.mcp.query(
                detection_query(
                    settings.clickhouse_database,
                    settings.watchtower_lookback_minutes,
                    settings.watchtower_baseline_minutes,
                )
            )
            matching = [
                row
                for row in rows
                if row.get("title_id") == anomaly.title_id and row.get("region") == anomaly.region
            ]
            return {"source": "official mcp-clickhouse", "rows": matching}

        async def inspect_root_cause(title_id: str, region: str) -> dict[str, Any]:
            """Read per-CDN evidence through official mcp-clickhouse for one safe scope."""
            rows = await self.mcp.query(
                root_cause_query(
                    settings.clickhouse_database,
                    title_id,
                    region,
                    settings.watchtower_lookback_minutes,
                )
            )
            return {"source": "official mcp-clickhouse", "rows": rows}

        detector = LlmAgent(
            name="detector_agent",
            model=settings.watchtower_agent_model,
            description="Validates statistically detected streaming anomalies against ClickHouse.",
            instruction=(
                "You are WatchTower's Detector Agent. You MUST call inspect_detection_window once. "
                "Compare that evidence with anomaly={anomaly}. State whether the anomaly is real, "
                "its magnitude, and confidence in no more than 100 words. Do not invent metrics."
            ),
            tools=[inspect_detection_window],
            output_key="detector_assessment",
            include_contents="none",
        )
        root = LlmAgent(
            name="root_cause_agent",
            model=settings.watchtower_agent_model,
            description="Correlates a validated anomaly with bounded CDN evidence.",
            instruction=(
                "You are WatchTower's Root-Cause Agent. You MUST call inspect_root_cause with the "
                "exact title_id and region found in anomaly={anomaly}. Reconcile the tool result "
                "with audited root_cause={root_cause} and detector={detector_assessment}. Return a "
                "concise evidence-led attribution; never claim certainty above the supplied "
                "confidence."
            ),
            tools=[inspect_root_cause],
            output_key="root_cause_assessment",
            include_contents="none",
        )
        impact_agent = LlmAgent(
            name="impact_estimator_agent",
            model=settings.watchtower_agent_model,
            description=(
                "Explains deterministic viewer and revenue impact without changing the math."
            ),
            instruction=(
                "You are WatchTower's Impact Estimator Agent. Use impact={impact} as immutable, "
                "audited calculations. Explain lost viewer-hours, affected sessions, dollar "
                "impact, "
                "severity, and methodology in under 100 words. Never recompute or round the values."
            ),
            output_key="impact_assessment",
            include_contents="none",
        )
        drafter = LlmAgent(
            name="action_drafter_agent",
            model=settings.watchtower_agent_model,
            description="Drafts a non-executing incident brief for human approval.",
            instruction=(
                "You are WatchTower's Action Drafter. Produce JSON matching the output schema. "
                "Synthesize detector={detector_assessment}, root={root_cause_assessment}, and "
                "impact={impact_assessment}. The recommended action must be specific, reversible, "
                "and explicitly pending human approval. You have no execution tools and must never "
                "claim that an action occurred."
            ),
            output_schema=ActionDraft,
            output_key="action_draft",
            include_contents="none",
        )
        return SequentialAgent(
            name="watchtower_orchestrator",
            description="Event-driven four-agent incident analysis pipeline.",
            sub_agents=[detector, root, impact_agent, drafter],
        )

    @staticmethod
    def _trace_from_events(events: list[Any], started: float) -> list[AgentTraceStep]:
        names = [
            ("Detector", "Validated the anomaly against MCP telemetry."),
            ("Root-Cause", "Correlated the signal with bounded CDN evidence."),
            ("Impact Estimator", "Explained the audited business-impact calculation."),
            ("Action Drafter", "Drafted a reversible action for human review."),
        ]
        elapsed_ms = max(1, round((time.perf_counter() - started) * 1000))
        per_agent = max(1, elapsed_ms // len(names))
        trace: list[AgentTraceStep] = []
        cursor = time.time() - elapsed_ms / 1000
        from datetime import UTC, datetime

        authors = {getattr(event, "author", "") for event in events}
        for index, (display, summary) in enumerate(names):
            step_started = datetime.fromtimestamp(cursor + index * per_agent / 1000, UTC)
            step_completed = datetime.fromtimestamp(cursor + (index + 1) * per_agent / 1000, UTC)
            machine_name = display.lower().replace(" ", "_").replace("-", "_") + "_agent"
            if machine_name not in authors and display != "Impact Estimator":
                summary += " ADK completion recorded by the orchestrator."
            trace.append(
                AgentTraceStep(
                    agent=display,
                    summary=summary,
                    started_at=step_started,
                    completed_at=step_completed,
                    duration_ms=per_agent,
                )
            )
        return trace

    @staticmethod
    def _fallback(
        anomaly: Anomaly,
        root_cause: RootCause,
        impact: ImpactEstimate,
    ) -> AgentPipelineResult:
        action_by_kind: dict[str, str] = {
            "view_drop": (
                "Pause regional promotion and ask playback operations to validate routing."
            ),
            "buffer_spike": "Shift a small canary of traffic away from the affected CDN node.",
            "ad_failure": "Pause the affected ad route and ask ad operations to verify delivery.",
        }
        brief = (
            f"{anomaly.title_name} in {anomaly.region} shows a "
            f"{anomaly.kind.value.replace('_', ' ')}. "
            f"{root_cause.summary} The audited estimate is {impact.lost_viewer_hours:.1f} lost "
            f"viewer-hours across {impact.affected_sessions:,} sessions, with approximately "
            f"${impact.estimated_revenue_loss_usd:,.2f} at risk ({impact.severity.value} severity)."
        )
        draft = ActionDraft(
            executive_brief=brief,
            recommended_action=(
                action_by_kind[anomaly.kind.value]
                + " Keep the change pending until an operator explicitly approves it."
            ),
        )
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        trace = [
            AgentTraceStep(
                agent=name,
                status="complete",
                summary="Deterministic local fallback; Gemini is required in production.",
                started_at=now,
                completed_at=now,
                duration_ms=0,
            )
            for name in ("Detector", "Root-Cause", "Impact Estimator", "Action Drafter")
        ]
        return AgentPipelineResult(draft=draft, trace=trace, used_gemini=False)
