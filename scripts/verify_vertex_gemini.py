"""One controlled real-Gemini verification using Vertex AI and ClickHouse Cloud."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from watchtower.agents import AgentPipeline
from watchtower.config import WATCHTOWER_PROJECT_ID, Settings
from watchtower.detection import Detector
from watchtower.impact import ImpactEstimator
from watchtower.mcp_client import OfficialClickHouseMcpClient
from watchtower.models import MetricSnapshot, TelemetryEvent
from watchtower.repository import ClickHouseRepository
from watchtower.root_cause import RootCauseAnalyzer
from watchtower.sql import detection_query, root_cause_query


async def verify() -> None:
    settings = Settings().model_copy(
        update={"watchtower_env": "production", "watchtower_bootstrap_schema": False}
    )
    if settings.google_cloud_project != WATCHTOWER_PROJECT_ID:
        raise RuntimeError("Refusing Gemini verification outside the WatchTower project.")
    if not settings.google_genai_use_vertexai:
        raise RuntimeError("Gemini verification must use Vertex AI.")

    repository = ClickHouseRepository(settings)
    mcp = OfficialClickHouseMcpClient(settings)
    try:
        repository.initialize()
        now = datetime.now(UTC)
        unique = uuid4().hex[:12]
        title_id = f"gemini-verification-{unique}"
        region = f"verification-{unique}"
        baseline = [
            TelemetryEvent(
                timestamp=now - timedelta(minutes=60 - minute),
                title_id=title_id,
                region=region,
                cdn_node="vertex-edge-01",
                views=140,
                starts=150,
                completions=120,
                buffer_events=2,
                buffer_seconds=9,
                ad_impressions=390,
                ad_errors=2,
            )
            for minute in range(50)
        ]
        current = [
            TelemetryEvent(
                timestamp=now - timedelta(seconds=cycle),
                title_id=title_id,
                region=region,
                cdn_node="vertex-edge-02",
                views=135,
                starts=150,
                completions=91,
                buffer_events=68,
                buffer_seconds=410,
                ad_impressions=380,
                ad_errors=3,
                anomaly_tag="buffer_spike",
            )
            for cycle in range(10)
        ]
        repository.insert_events([*baseline, *current])

        rows = await mcp.query(
            detection_query(
                settings.clickhouse_database,
                settings.watchtower_lookback_minutes,
                settings.watchtower_baseline_minutes,
            )
        )
        row = next(item for item in rows if item["title_id"] == title_id)
        snapshot = MetricSnapshot(
            title_id=title_id,
            title_name=title_id,
            region=region,
            current_views=float(row["current_views"]),
            baseline_views=float(row["baseline_views"]),
            current_buffer_rate=float(row["current_buffer_rate"]),
            baseline_buffer_rate=float(row["baseline_buffer_rate"]),
            current_ad_error_rate=float(row["current_ad_error_rate"]),
            baseline_ad_error_rate=float(row["baseline_ad_error_rate"]),
            current_starts=float(row["current_starts"]),
            current_completions=float(row["current_completions"]),
        )
        anomaly = Detector().detect(snapshot)
        if anomaly is None:
            raise RuntimeError("The planted Gemini verification anomaly was not detected.")
        root_rows = await mcp.query(
            root_cause_query(
                settings.clickhouse_database,
                title_id,
                region,
                settings.watchtower_lookback_minutes,
            )
        )
        root = RootCauseAnalyzer().analyze(anomaly, root_rows)
        impact = ImpactEstimator().estimate(anomaly, snapshot)
        result = await AgentPipeline(settings, mcp).run(anomaly, root, impact)
        if not result.used_gemini:
            raise RuntimeError("Gemini fell back locally instead of completing through Vertex AI.")
        if len(result.trace) != 4:
            raise RuntimeError("Vertex AI did not produce the required four-stage trace.")

        print(f"Vertex AI project: {settings.google_cloud_project}")
        print(f"Gemini model: {settings.watchtower_agent_model}")
        print("Real Gemini execution: pass")
        print("Four ADK agent stages: pass")
        print("Official MCP evidence tools inside agents: pass")
        print("Structured human-gated action draft: pass")
    finally:
        await mcp.close()


if __name__ == "__main__":
    asyncio.run(verify())
