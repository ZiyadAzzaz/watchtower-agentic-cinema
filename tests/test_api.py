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
