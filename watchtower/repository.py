from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any, Protocol
from uuid import UUID

import clickhouse_connect

from watchtower.catalog import TITLES
from watchtower.config import Settings
from watchtower.models import Incident, IncidentStatus, TelemetryEvent


class Repository(Protocol):
    def initialize(self) -> None: ...
    def insert_events(self, events: Iterable[TelemetryEvent]) -> int: ...
    def event_count(self) -> int: ...
    def recent_event_count(self, minutes: int) -> int: ...
    def save_incident(self, incident: Incident) -> None: ...
    def list_incidents(self, limit: int = 30) -> list[Incident]: ...
    def get_incident(self, incident_id: UUID) -> Incident | None: ...


class ClickHouseRepository:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: Any | None = None
        self._client_lock = Lock()

    @property
    def client(self) -> Any:
        """Connect on first use.

        Cloud Run must bind its port before a possibly idle ClickHouse Cloud
        service finishes waking, so no network handshake may run while the
        application is being constructed.
        """
        client = self._client
        if client is not None:
            return client
        with self._client_lock:
            if self._client is None:
                self._client = clickhouse_connect.get_client(
                    host=self.settings.clickhouse_host,
                    port=self.settings.clickhouse_port,
                    username=self.settings.clickhouse_user,
                    password=self.settings.clickhouse_password.get_secret_value(),
                    database=self.settings.clickhouse_database,
                    secure=self.settings.clickhouse_secure,
                    verify=self.settings.clickhouse_verify,
                    connect_timeout=15,
                    send_receive_timeout=60,
                )
            return self._client

    def initialize(self) -> None:
        database = self.settings.clickhouse_database
        if self.settings.watchtower_bootstrap_schema:
            self.client.command(f"CREATE DATABASE IF NOT EXISTS {database}")
            self.client.command(
                f"""
            CREATE TABLE IF NOT EXISTS {database}.titles (
              title_id LowCardinality(String),
              name String,
              genre LowCardinality(String),
              description String,
              accent_from FixedString(7),
              accent_to FixedString(7),
              baseline_popularity Float32
            ) ENGINE = ReplacingMergeTree ORDER BY title_id
                """
            )
            self.client.command(
                f"""
            CREATE TABLE IF NOT EXISTS {database}.telemetry_events (
              event_id UUID,
              event_time DateTime64(3, 'UTC'),
              title_id LowCardinality(String),
              region LowCardinality(String),
              cdn_node LowCardinality(String),
              views UInt32,
              starts UInt32,
              completions UInt32,
              buffer_events UInt32,
              buffer_seconds Float64,
              ad_impressions UInt32,
              ad_errors UInt32,
              anomaly_tag LowCardinality(String)
            ) ENGINE = MergeTree
            PARTITION BY toDate(event_time)
            ORDER BY (title_id, region, event_time, event_id)
            TTL event_time + INTERVAL 14 DAY DELETE
            SETTINGS index_granularity = 8192
                """
            )
            self.client.command(
                f"""
            CREATE TABLE IF NOT EXISTS {database}.incidents (
              incident_id UUID,
              status LowCardinality(String),
              severity LowCardinality(String),
              title_id LowCardinality(String),
              region LowCardinality(String),
              created_at DateTime64(3, 'UTC'),
              updated_at DateTime64(3, 'UTC'),
              version UInt32,
              payload String
            ) ENGINE = ReplacingMergeTree(version)
            ORDER BY incident_id
                """
            )
        elif not self.client.ping():
            raise RuntimeError("ClickHouse health check failed.")
        self.client.insert(
            f"{database}.titles",
            [
                [
                    title.id,
                    title.name,
                    title.genre,
                    title.description,
                    title.accent_from,
                    title.accent_to,
                    title.baseline_popularity,
                ]
                for title in TITLES
            ],
            column_names=[
                "title_id",
                "name",
                "genre",
                "description",
                "accent_from",
                "accent_to",
                "baseline_popularity",
            ],
        )

    def insert_events(self, events: Iterable[TelemetryEvent]) -> int:
        rows = list(events)
        if not rows:
            return 0
        self.client.insert(
            f"{self.settings.clickhouse_database}.telemetry_events",
            [
                [
                    event.event_id,
                    event.timestamp,
                    event.title_id,
                    event.region,
                    event.cdn_node,
                    event.views,
                    event.starts,
                    event.completions,
                    event.buffer_events,
                    event.buffer_seconds,
                    event.ad_impressions,
                    event.ad_errors,
                    event.anomaly_tag,
                ]
                for event in rows
            ],
            column_names=[
                "event_id",
                "event_time",
                "title_id",
                "region",
                "cdn_node",
                "views",
                "starts",
                "completions",
                "buffer_events",
                "buffer_seconds",
                "ad_impressions",
                "ad_errors",
                "anomaly_tag",
            ],
        )
        return len(rows)

    def event_count(self) -> int:
        result = self.client.query(
            f"SELECT count() FROM {self.settings.clickhouse_database}.telemetry_events"
        )
        return int(result.first_row[0])

    def recent_event_count(self, minutes: int) -> int:
        window = int(minutes)
        if window <= 0:
            raise ValueError("Recency window must be positive.")
        result = self.client.query(
            f"SELECT count() FROM {self.settings.clickhouse_database}.telemetry_events "
            f"WHERE event_time >= now64(3, 'UTC') - INTERVAL {window} MINUTE"
        )
        return int(result.first_row[0])

    def save_incident(self, incident: Incident) -> None:
        self.client.insert(
            f"{self.settings.clickhouse_database}.incidents",
            [
                [
                    incident.id,
                    incident.status.value,
                    incident.impact.severity.value,
                    incident.anomaly.title_id,
                    incident.anomaly.region,
                    incident.created_at,
                    incident.updated_at,
                    incident.version,
                    incident.model_dump_json(),
                ]
            ],
            column_names=[
                "incident_id",
                "status",
                "severity",
                "title_id",
                "region",
                "created_at",
                "updated_at",
                "version",
                "payload",
            ],
        )

    def list_incidents(self, limit: int = 30) -> list[Incident]:
        result = self.client.query(
            f"""
            SELECT argMax(payload, version) AS payload
            FROM {self.settings.clickhouse_database}.incidents
            GROUP BY incident_id
            ORDER BY max(updated_at) DESC
            LIMIT {{limit:UInt16}}
            """,
            parameters={"limit": limit},
        )
        return [Incident.model_validate_json(row[0]) for row in result.result_rows]

    def get_incident(self, incident_id: UUID) -> Incident | None:
        result = self.client.query(
            f"""
            SELECT argMax(payload, version)
            FROM {self.settings.clickhouse_database}.incidents
            WHERE incident_id = {{incident_id:UUID}}
            GROUP BY incident_id
            LIMIT 1
            """,
            parameters={"incident_id": str(incident_id)},
        )
        return Incident.model_validate_json(result.first_row[0]) if result.result_rows else None


class MemoryRepository:
    def __init__(self):
        self.events: list[TelemetryEvent] = []
        self.incidents: dict[UUID, Incident] = {}
        self._lock = Lock()

    def initialize(self) -> None:
        return None

    def insert_events(self, events: Iterable[TelemetryEvent]) -> int:
        rows = list(events)
        with self._lock:
            self.events.extend(rows)
        return len(rows)

    def event_count(self) -> int:
        return len(self.events)

    def recent_event_count(self, minutes: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(minutes=int(minutes))
        return sum(1 for event in self.events if event.timestamp >= cutoff)

    def save_incident(self, incident: Incident) -> None:
        with self._lock:
            self.incidents[incident.id] = incident.model_copy(deep=True)

    def list_incidents(self, limit: int = 30) -> list[Incident]:
        values = sorted(self.incidents.values(), key=lambda item: item.updated_at, reverse=True)
        return [item.model_copy(deep=True) for item in values[:limit]]

    def get_incident(self, incident_id: UUID) -> Incident | None:
        value = self.incidents.get(incident_id)
        return value.model_copy(deep=True) if value else None

    def decide(
        self,
        incident_id: UUID,
        status: IncidentStatus,
        note: str = "",
    ) -> Incident | None:
        with self._lock:
            incident = self.incidents.get(incident_id)
            if not incident:
                return None
            incident.status = status
            incident.decision_note = note
            incident.updated_at = datetime.now(UTC)
            incident.version += 1
            return incident.model_copy(deep=True)


def incident_from_json(value: str | dict[str, Any]) -> Incident:
    return (
        Incident.model_validate_json(value)
        if isinstance(value, str)
        else Incident.model_validate(value)
    )
