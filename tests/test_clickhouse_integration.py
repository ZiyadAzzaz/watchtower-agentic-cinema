from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from watchtower.config import Settings
from watchtower.mcp_client import OfficialClickHouseMcpClient
from watchtower.models import IncidentStatus, TelemetryEvent
from watchtower.repository import ClickHouseRepository
from watchtower.runtime import WatchtowerRuntime


def local_settings() -> Settings:
    return Settings(
        watchtower_env="test",
        watchtower_bootstrap_schema=False,
        clickhouse_host="127.0.0.1",
        clickhouse_port=8123,
        clickhouse_database="watchtower",
        clickhouse_user="watchtower_app",
        clickhouse_password="local-app-only",
        clickhouse_mcp_user="watchtower_mcp",
        clickhouse_mcp_password="local-mcp-only",
        clickhouse_secure=False,
        clickhouse_verify=False,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_clickhouse_mcp_pipeline_and_read_only_guard() -> None:
    settings = local_settings()
    mcp = OfficialClickHouseMcpClient(settings)
    runtime = WatchtowerRuntime(settings, ClickHouseRepository(settings), mcp)
    try:
        await runtime.initialize()
        now = datetime.now(UTC)
        unique = uuid4().hex[:10]
        title_id = f"integration-{unique}"
        region = f"test-region-{unique}"
        baseline = [
            TelemetryEvent(
                timestamp=now - timedelta(minutes=60 - minute),
                title_id=title_id,
                region=region,
                cdn_node="me-edge-01",
                views=100,
                starts=110,
                completions=85,
                buffer_events=2,
                buffer_seconds=10,
                ad_impressions=280,
                ad_errors=2,
            )
            for minute in range(50)
        ]
        current = [
            TelemetryEvent(
                timestamp=now - timedelta(seconds=cycle),
                title_id=title_id,
                region=region,
                cdn_node="me-edge-02",
                views=100,
                starts=110,
                completions=72,
                buffer_events=48,
                buffer_seconds=300,
                ad_impressions=270,
                ad_errors=3,
                anomaly_tag="buffer_spike",
            )
            for cycle in range(10)
        ]
        runtime.repository.insert_events([*baseline, *current])

        incidents = await runtime.scan()
        incident = next(item for item in incidents if item.anomaly.title_id == title_id)
        assert incident.root_cause.primary_value == "me-edge-02"
        assert incident.status == IncidentStatus.PENDING_APPROVAL
        assert runtime.repository.event_count() >= 1200

        with pytest.raises(RuntimeError, match="rejected"):
            await mcp.query("DROP TABLE watchtower.telemetry_events LIMIT 1")
    finally:
        await runtime.close()
