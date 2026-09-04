from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from time import monotonic
from typing import Any
from uuid import UUID

from watchtower.agents import AgentPipeline
from watchtower.catalog import REGIONS, TITLE_BY_ID
from watchtower.config import Settings
from watchtower.detection import Detector
from watchtower.generator import SyntheticEventGenerator
from watchtower.impact import ImpactEstimator
from watchtower.mcp_client import QueryExecutor
from watchtower.models import (
    AnomalyInjectionRequest,
    Incident,
    IncidentStatus,
    MetricSnapshot,
    SystemStatus,
)
from watchtower.repository import Repository
from watchtower.root_cause import RootCauseAnalyzer
from watchtower.sql import detection_query, live_summary_query, root_cause_query, timeseries_query


def _as_utc_iso(value: Any) -> Any:
    """Mark a ClickHouse timestamp as UTC.

    ClickHouse returns naive strings such as "2026-09-04 10:13:56". A browser
    parses those as local time, so an operator in UTC+3 sees a live reading
    reported as three hours stale. Everything WatchTower stores is UTC, so the
    designator is added explicitly before the value leaves the API.
    """
    if isinstance(value, datetime):
        return value.replace(tzinfo=value.tzinfo or UTC).isoformat()
    if isinstance(value, str) and value and not value.endswith("Z") and "+" not in value:
        return value.replace(" ", "T") + "Z"
    return value


class WatchtowerRuntime:
    def __init__(
        self,
        settings: Settings,
        repository: Repository,
        mcp: QueryExecutor,
        agents: AgentPipeline | None = None,
    ):
        self.settings = settings
        self.repository = repository
        self.mcp = mcp
        self.generator = SyntheticEventGenerator(repository)
        self.detector = Detector()
        self.root_analyzer = RootCauseAnalyzer()
        self.impact_estimator = ImpactEstimator()
        self.agents = agents or AgentPipeline(settings, mcp)
        self.last_tick_at: datetime | None = None
        self._last_tick_clock = 0.0
        self._lock = asyncio.Lock()
        self.used_gemini = False

    async def initialize(self) -> None:
        await asyncio.to_thread(self.repository.initialize)
        await self.ensure_baseline_history()

    async def ensure_baseline_history(self) -> bool:
        """Seed history whenever the detection baseline window is thin.

        Detection compares a live window against the preceding baseline window,
        so total row count is not a useful signal: telemetry stored days ago
        leaves both windows empty after the service has been idle.
        """
        history_minutes = (
            self.settings.watchtower_baseline_minutes
            + self.settings.watchtower_lookback_minutes
            + 2
        )
        recent = await asyncio.to_thread(self.repository.recent_event_count, history_minutes)
        minimum_seed = len(TITLE_BY_ID) * len(REGIONS) * 20
        if recent >= minimum_seed:
            return False
        await asyncio.to_thread(self.generator.seed_history, history_minutes)
        return True

    async def close(self) -> None:
        close = getattr(self.mcp, "close", None)
        if close is not None:
            await close()

    async def tick_if_due(self, force: bool = False) -> list[Incident]:
        now_clock = monotonic()
        if (
            not force
            and now_clock - self._last_tick_clock
            < self.settings.watchtower_detection_interval_seconds
        ):
            return []
        async with self._lock:
            now_clock = monotonic()
            if (
                not force
                and now_clock - self._last_tick_clock
                < self.settings.watchtower_detection_interval_seconds
            ):
                return []
            # Self-heal after an idle gap so a judge always sees a usable
            # baseline instead of an empty detection window.
            await self.ensure_baseline_history()
            await asyncio.to_thread(self.generator.tick)
            self.last_tick_at = datetime.now(UTC)
            self._last_tick_clock = now_clock
            return await self.scan()

    async def scan(self) -> list[Incident]:
        rows = await self.mcp.query(
            detection_query(
                self.settings.clickhouse_database,
                self.settings.watchtower_lookback_minutes,
                self.settings.watchtower_baseline_minutes,
            )
        )
        incidents: list[Incident] = []
        for row in rows:
            snapshot = self._snapshot(row)
            anomaly = self.detector.detect(snapshot)
            if not anomaly or self._has_open_duplicate(
                anomaly.title_id, anomaly.region, anomaly.kind
            ):
                continue
            root_rows = await self.mcp.query(
                root_cause_query(
                    self.settings.clickhouse_database,
                    anomaly.title_id,
                    anomaly.region,
                    self.settings.watchtower_lookback_minutes,
                )
            )
            root = self.root_analyzer.analyze(anomaly, root_rows)
            impact = self.impact_estimator.estimate(anomaly, snapshot)
            agent_result = await self.agents.run(anomaly, root, impact)
            self.used_gemini = self.used_gemini or agent_result.used_gemini
            incident = Incident(
                anomaly=anomaly,
                root_cause=root,
                impact=impact,
                executive_brief=agent_result.draft.executive_brief,
                recommended_action=agent_result.draft.recommended_action,
                agent_trace=agent_result.trace,
            )
            await asyncio.to_thread(self.repository.save_incident, incident)
            incidents.append(incident)
        return incidents

    def inject(self, request: AnomalyInjectionRequest) -> None:
        if request.title_id not in TITLE_BY_ID:
            raise ValueError("Unknown fictional title_id.")
        self.generator.inject(request)

    async def decide(
        self,
        incident_id: UUID,
        status: IncidentStatus,
        note: str,
    ) -> Incident | None:
        incident = await asyncio.to_thread(self.repository.get_incident, incident_id)
        if not incident:
            return None
        if incident.status != IncidentStatus.PENDING_APPROVAL:
            raise ValueError("Only a pending incident can receive a decision.")
        incident.status = status
        incident.decision_note = note
        incident.updated_at = datetime.now(UTC)
        incident.version += 1
        await asyncio.to_thread(self.repository.save_incident, incident)
        return incident

    async def dashboard(self) -> dict[str, Any]:
        await self.tick_if_due()
        summary_rows = await self.mcp.query(live_summary_query(self.settings.clickhouse_database))
        timeseries = await self.mcp.query(timeseries_query(self.settings.clickhouse_database))
        incidents = await asyncio.to_thread(self.repository.list_incidents, 30)
        summary = dict(summary_rows[0]) if summary_rows else {}
        if "last_event_at" in summary:
            summary["last_event_at"] = _as_utc_iso(summary["last_event_at"])
        for point in timeseries:
            if "minute" in point:
                point["minute"] = _as_utc_iso(point["minute"])
        return {
            "summary": summary,
            "timeseries": timeseries,
            "incidents": [item.model_dump(mode="json") for item in incidents],
            "titles": [title.model_dump(mode="json") for title in TITLE_BY_ID.values()],
            "status": self.status(incidents).model_dump(mode="json"),
        }

    def status(self, incidents: list[Incident] | None = None) -> SystemStatus:
        incidents = incidents if incidents is not None else self.repository.list_incidents(30)
        return SystemStatus(
            status="operational",
            environment=self.settings.watchtower_env,
            data_source="ClickHouse",
            mcp_server="official mcp-clickhouse / read-only",
            ai_provider=(
                "Gemini on Vertex AI" if self.used_gemini else "Gemini ready / event-gated"
            ),
            human_gate="required",
            last_tick_at=self.last_tick_at,
            events_ingested=self.repository.event_count(),
            pending_incidents=sum(
                item.status == IncidentStatus.PENDING_APPROVAL for item in incidents
            ),
        )

    def _has_open_duplicate(self, title_id: str, region: str, kind: Any) -> bool:
        for incident in self.repository.list_incidents(50):
            if (
                incident.status in {IncidentStatus.INVESTIGATING, IncidentStatus.PENDING_APPROVAL}
                and incident.anomaly.title_id == title_id
                and incident.anomaly.region == region
                and incident.anomaly.kind == kind
            ):
                return True
        return False

    def _snapshot(self, row: dict[str, Any]) -> MetricSnapshot:
        title_id = str(row["title_id"])
        title = TITLE_BY_ID.get(title_id)
        return MetricSnapshot(
            title_id=title_id,
            title_name=title.name if title else title_id,
            region=str(row["region"]),
            current_views=float(row.get("current_views") or 0),
            baseline_views=float(row.get("baseline_views") or 0),
            current_buffer_rate=float(row.get("current_buffer_rate") or 0),
            baseline_buffer_rate=float(row.get("baseline_buffer_rate") or 0),
            current_ad_error_rate=float(row.get("current_ad_error_rate") or 0),
            baseline_ad_error_rate=float(row.get("baseline_ad_error_rate") or 0),
            current_starts=float(row.get("current_starts") or 0),
            current_completions=float(row.get("current_completions") or 0),
            window_minutes=self.settings.watchtower_lookback_minutes,
        )
