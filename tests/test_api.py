import asyncio

from fastapi.testclient import TestClient

from watchtower.api import create_app
from watchtower.config import Settings
from watchtower.mcp_client import StaticQueryExecutor
from watchtower.repository import MemoryRepository
from watchtower.runtime import WatchtowerRuntime


def make_client() -> TestClient:
    runtime = WatchtowerRuntime(
        Settings(watchtower_env="test", _env_file=None),
        MemoryRepository(),
        StaticQueryExecutor([]),
    )
    return TestClient(create_app(runtime))


def test_health_and_dashboard_shell() -> None:
    with make_client() as client:
        health = client.get("/healthz")
        assert health.status_code == 200
        assert health.json()["service"] == "watchtower"
        # Cloud Run reserves the exact path "/healthz" at its frontend.
        aliased = client.get("/api/healthz")
        assert aliased.status_code == 200
        assert aliased.json()["service"] == "watchtower"
        assert client.get("/health").json()["service"] == "watchtower"
        assert client.get("/api/readyz").status_code == 200
        assert client.get("/ready").status_code == 200
        assert health.headers["x-content-type-options"] == "nosniff"
        assert "frame-ancestors 'none'" in health.headers["content-security-policy"]
        page = client.get("/")
        assert page.status_code == 200
        assert "Human approval required" in page.text
        assert "Simulate incident" in page.text


def test_invalid_title_is_rejected() -> None:
    with make_client() as client:
        response = client.post(
            "/api/admin/inject",
            json={
                "kind": "buffer_spike",
                "title_id": "not-a-real-title",
                "region": "MENA",
                "duration_cycles": 4,
                "magnitude": 0.8,
            },
        )
        assert response.status_code == 422


def test_production_listens_while_runtime_initializes() -> None:
    class SlowRuntime:
        settings = Settings(
            watchtower_env="production",
            watchtower_bootstrap_schema=False,
            watchtower_admin_token="test-admin-token",
            clickhouse_password="test-app-password",
            clickhouse_mcp_password="test-mcp-password",
            clickhouse_secure=True,
            clickhouse_verify=True,
            _env_file=None,
        )

        async def initialize(self) -> None:
            await asyncio.Event().wait()

        async def close(self) -> None:
            return None

    with TestClient(create_app(SlowRuntime())) as client:
        assert client.get("/healthz").status_code == 200
        readiness = client.get("/readyz")
        assert readiness.status_code == 503
        assert readiness.json()["detail"] == "Runtime is initializing"


def test_repository_construction_opens_no_connection(monkeypatch) -> None:
    """Cloud Run must bind its port before ClickHouse is reachable."""
    import watchtower.repository as repository_module

    def fail(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("ClickHouse must not be contacted during construction")

    monkeypatch.setattr(repository_module.clickhouse_connect, "get_client", fail)
    repository = repository_module.ClickHouseRepository(
        Settings(
            watchtower_env="production",
            watchtower_bootstrap_schema=False,
            watchtower_admin_token="test-admin-token",
            clickhouse_password="test-app-password",
            clickhouse_mcp_password="test-mcp-password",
            clickhouse_secure=True,
            clickhouse_verify=True,
            _env_file=None,
        )
    )
    assert repository._client is None
