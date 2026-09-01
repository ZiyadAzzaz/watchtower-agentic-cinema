from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AnomalyKind(StrEnum):
    VIEW_DROP = "view_drop"
    BUFFER_SPIKE = "buffer_spike"
    AD_FAILURE = "ad_failure"


class IncidentStatus(StrEnum):
    INVESTIGATING = "investigating"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    DISMISSED = "dismissed"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Title(BaseModel):
    id: str
    name: str
    genre: str
    description: str
    accent_from: str
    accent_to: str
    baseline_popularity: float = Field(gt=0)


class TelemetryEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    title_id: str
    region: str
    cdn_node: str
    views: int = Field(ge=0)
    starts: int = Field(ge=0)
    completions: int = Field(ge=0)
    buffer_events: int = Field(ge=0)
    buffer_seconds: float = Field(ge=0)
    ad_impressions: int = Field(ge=0)
    ad_errors: int = Field(ge=0)
    anomaly_tag: str = ""


class MetricSnapshot(BaseModel):
    title_id: str
    region: str
    title_name: str = ""
    current_views: float = 0
    baseline_views: float = 0
    current_buffer_rate: float = 0
    baseline_buffer_rate: float = 0
    current_ad_error_rate: float = 0
    baseline_ad_error_rate: float = 0
    current_starts: float = 0
    current_completions: float = 0
    window_minutes: int = 5


class Anomaly(BaseModel):
    kind: AnomalyKind
    title_id: str
    title_name: str
    region: str
    observed: float
    baseline: float
    deviation_percent: float
    confidence: float = Field(ge=0, le=1)
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RootCause(BaseModel):
    summary: str
    primary_dimension: str
    primary_value: str
    evidence: list[str]
    confidence: float = Field(ge=0, le=1)


class ImpactEstimate(BaseModel):
    lost_viewer_hours: float = Field(ge=0)
    estimated_revenue_loss_usd: float = Field(ge=0)
    affected_sessions: int = Field(ge=0)
    severity: Severity
    methodology: str


class AgentTraceStep(BaseModel):
    agent: str
    status: Literal["complete", "failed"] = "complete"
    summary: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int = Field(ge=0)


class Incident(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    anomaly: Anomaly
    root_cause: RootCause
    impact: ImpactEstimate
    executive_brief: str
    recommended_action: str
    status: IncidentStatus = IncidentStatus.PENDING_APPROVAL
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: int = 1
    agent_trace: list[AgentTraceStep] = Field(default_factory=list)
    decision_note: str = ""


class AnomalyInjectionRequest(BaseModel):
    kind: AnomalyKind
    title_id: str
    region: str
    duration_cycles: int = Field(default=4, ge=2, le=12)
    magnitude: float = Field(default=0.75, ge=0.3, le=0.95)


class IncidentDecisionRequest(BaseModel):
    note: str = Field(default="", max_length=300)


class SystemStatus(BaseModel):
    status: str
    environment: str
    data_source: str
    mcp_server: str
    ai_provider: str
    human_gate: str
    last_tick_at: datetime | None = None
    events_ingested: int = 0
    pending_incidents: int = 0
