"""Non-destructive end-to-end verification against configured ClickHouse Cloud."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from watchtower.config import Settings
from watchtower.mcp_client import OfficialClickHouseMcpClient
from watchtower.models import IncidentStatus, TelemetryEvent
from watchtower.repository import ClickHouseRepository
from watchtower.runtime import WatchtowerRuntime


async def verify() -> None:
    settings = Settings().model_copy(
        update={"watchtower_env": "test", "watchtower_bootstrap_schema": False}
    )
    if not settings.clickhouse_secure or not settings.clickhouse_verify:
        raise RuntimeError("Cloud verification requires verified TLS.")
    if settings.clickhouse_user != "watchtower_app":
        raise RuntimeError("Cloud verification requires the scoped watchtower_app identity.")
    if settings.clickhouse_mcp_user != "watchtower_mcp":
        raise RuntimeError("Cloud verification requires the scoped watchtower_mcp identity.")

    mcp = OfficialClickHouseMcpClient(settings)
    runtime = WatchtowerRuntime(settings, ClickHouseRepository(settings), mcp)
    try:
        await runtime.initialize()
        now = datetime.now(UTC)
        unique = uuid4().hex[:12]
        title_id = f"cloud-verification-{unique}"
        region = f"verification-{unique}"
        baseline = [
            TelemetryEvent(
                timestamp=now - timedelta(minutes=60 - minute),
                title_id=title_id,
                region=region,
                cdn_node="cloud-edge-01",
                views=120,
                starts=130,
                completions=102,
                buffer_events=2,
                buffer_seconds=9,
                ad_impressions=330,
                ad_errors=2,
            )
            for minute in range(50)
        ]
        current = [
            TelemetryEvent(
                timestamp=now - timedelta(seconds=cycle),
                title_id=title_id,
                region=region,
                cdn_node="cloud-edge-02",
                views=115,
                starts=130,
                completions=80,
                buffer_events=58,
                buffer_seconds=360,
                ad_impressions=320,
                ad_errors=3,
                anomaly_tag="buffer_spike",
            )
            for cycle in range(10)
        ]
        runtime.repository.insert_events([*baseline, *current])

        incidents = await runtime.scan()
        incident = next(item for item in incidents if item.anomaly.title_id == title_id)
        if incident.root_cause.primary_value != "cloud-edge-02":
            raise RuntimeError("Root-cause attribution did not match the planted edge node.")
        if len(incident.agent_trace) != 4:
            raise RuntimeError("The four-stage agent trace did not complete.")
        decided = await runtime.decide(
            incident.id,
            IncidentStatus.APPROVED,
            "Approved during non-destructive ClickHouse Cloud verification.",
        )
        if decided is None or decided.status != IncidentStatus.APPROVED:
            raise RuntimeError("Human decision persistence failed.")

        try:
            await mcp.query("DROP TABLE watchtower.telemetry_events LIMIT 1")
        except RuntimeError:
            destructive_rejected = True
        else:
            destructive_rejected = False
        if not destructive_rejected:
            raise RuntimeError("The MCP destructive-query guard did not reject the query.")

        print("ClickHouse Cloud TLS connection: pass")
        print("Scoped ingestion identity: pass")
        print("Official mcp-clickhouse read path: pass")
        print("Detector/root-cause/impact/four-stage trace: pass")
        print("Human approval persistence: pass")
        print("Destructive MCP query rejection: pass")
        print(f"Verified incident: {incident.id}")
    finally:
        await runtime.close()


if __name__ == "__main__":
    asyncio.run(verify())
