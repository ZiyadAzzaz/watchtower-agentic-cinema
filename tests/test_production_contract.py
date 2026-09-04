"""Contract tests for the behaviour that only broke in production.

Every case here maps to a defect that reached a real Cloud Run revision.
They are cheap, hermetic, and exist so the same class of failure cannot ship
again.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import watchtower.repository as repository_module
from watchtower.api import create_app
from watchtower.config import Settings
from watchtower.mcp_client import StaticQueryExecutor
from watchtower.repository import ClickHouseRepository, MemoryRepository
from watchtower.runtime import WatchtowerRuntime, _as_utc_iso


def production_settings() -> Settings:
    return Settings(
        watchtower_env="production",
        watchtower_bootstrap_schema=False,
        watchtower_admin_token="test-admin-token",
        clickhouse_password="test-app-password",
        clickhouse_mcp_password="test-mcp-password",
        clickhouse_secure=True,
        clickhouse_verify=True,
        _env_file=None,
    )


class StubAgents:
    async def run(self, anomaly, root_cause, impact):  # pragma: no cover - unused here
        raise AssertionError("agents must not run in these tests")


# --- Defect 13: the container never listened, because connecting blocked ------


def test_building_the_repository_never_touches_the_network(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise AssertionError("ClickHouse must not be contacted during construction")

    monkeypatch.setattr(repository_module.clickhouse_connect, "get_client", fail)
    repository = ClickHouseRepository(production_settings())
    assert getattr(repository._local, "client", None) is None


def test_production_serves_health_while_the_datastore_is_unreachable() -> None:
    """Cloud Run kills a container that does not bind its port in time."""

    class NeverReadyRuntime:
        settings = production_settings()

        async def initialize(self) -> None:
            await asyncio.Event().wait()

        async def close(self) -> None:
            return None

    with TestClient(create_app(NeverReadyRuntime())) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/readyz").status_code == 503
        # Operational endpoints stay closed until initialization succeeds.
        assert client.get("/api/dashboard").status_code == 503


# --- Defect 14: Cloud Run's frontend answers /healthz itself -----------------


@pytest.mark.parametrize("path", ["/healthz", "/health", "/api/healthz"])
def test_every_health_path_is_served(path: str) -> None:
    runtime = WatchtowerRuntime(
        Settings(watchtower_env="test", _env_file=None),
        MemoryRepository(),
        StaticQueryExecutor([]),
    )
    with TestClient(create_app(runtime)) as client:
        response = client.get(path)
        assert response.status_code == 200
        assert response.json()["service"] == "watchtower"


@pytest.mark.parametrize("path", ["/readyz", "/ready", "/api/readyz"])
def test_every_readiness_path_is_served(path: str) -> None:
    runtime = WatchtowerRuntime(
        Settings(watchtower_env="test", _env_file=None),
        MemoryRepository(),
        StaticQueryExecutor([]),
    )
    with TestClient(create_app(runtime)) as client:
        assert client.get(path).status_code == 200


# --- Defect 16: seeding was gated on total rows, so the baseline went stale ---


@pytest.mark.asyncio
async def test_history_older_than_the_baseline_window_is_reseeded() -> None:
    repository = MemoryRepository()
    runtime = WatchtowerRuntime(
        Settings(watchtower_env="test", _env_file=None),
        repository,
        StaticQueryExecutor([]),
        agents=StubAgents(),
    )
    stale = datetime.now(UTC) - timedelta(days=3)
    repository.insert_events(runtime.generator.generate_cycle(stale) * 40)
    assert repository.event_count() >= 1200, "plenty of rows in total"
    assert repository.recent_event_count(67) == 0, "but none inside the baseline window"

    assert await runtime.ensure_baseline_history() is True
    assert repository.recent_event_count(67) >= 1200
    assert await runtime.ensure_baseline_history() is False, "must not reseed a fresh baseline"


# --- Defect 17: naive timestamps were read as local time by the browser ------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-09-04 10:13:56.805000", "2026-09-04T10:13:56.805000Z"),
        ("2026-09-04 09:44:00", "2026-09-04T09:44:00Z"),
        ("2026-09-04T09:44:00Z", "2026-09-04T09:44:00Z"),
        ("2026-09-04T09:44:00+00:00", "2026-09-04T09:44:00+00:00"),
    ],
)
def test_timestamps_leave_the_api_marked_utc(raw: str, expected: str) -> None:
    assert _as_utc_iso(raw) == expected


# --- The human approval boundary --------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/admin/inject"),
        ("post", "/api/admin/tick"),
        ("post", "/api/incidents/00000000-0000-0000-0000-000000000000/approve"),
        ("post", "/api/incidents/00000000-0000-0000-0000-000000000000/dismiss"),
    ],
)
def test_control_endpoints_reject_a_caller_without_the_operator_token(
    method: str, path: str
) -> None:
    """The service is public; this boundary is the only thing guarding control."""

    class ReadyRuntime:
        settings = production_settings()

        async def initialize(self) -> None:
            return None

        async def close(self) -> None:
            return None

    with TestClient(create_app(ReadyRuntime())) as client:
        assert getattr(client, method)(path, json={}).status_code == 401
        wrong = getattr(client, method)(
            path, json={}, headers={"X-Watchtower-Token": "wrong-token"}
        )
        assert wrong.status_code == 401


def test_no_execution_tool_exists_anywhere_in_the_runtime() -> None:
    """The action agent drafts; it must never be able to act."""
    import pathlib

    forbidden = ("def execute_", "def remediate", "def apply_fix", "def restart_cdn")
    for source in pathlib.Path("watchtower").rglob("*.py"):
        text = source.read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in text, f"{source} defines an execution tool: {marker}"


def test_each_thread_gets_its_own_clickhouse_client(monkeypatch) -> None:
    """clickhouse_connect refuses concurrent queries on one session.

    Repository work runs through asyncio.to_thread, so two requests arriving at
    once would otherwise collide on a shared client and return 500.
    """
    import threading

    created: list[object] = []
    created_lock = threading.Lock()

    def fake_client(*args, **kwargs):
        client = object()
        with created_lock:
            created.append(client)
        return client

    monkeypatch.setattr(repository_module.clickhouse_connect, "get_client", fake_client)
    repository = ClickHouseRepository(production_settings())

    threads_count = 4
    # Hold every thread alive at once: a finished thread's id can be reused,
    # which would hide a shared client rather than expose it.
    barrier = threading.Barrier(threads_count)
    seen: list[object] = []
    seen_lock = threading.Lock()

    def grab() -> None:
        client = repository.client
        # A second access on the same thread must reuse, not reconnect.
        assert repository.client is client
        barrier.wait(timeout=10)
        with seen_lock:
            seen.append(client)

    threads = [threading.Thread(target=grab) for _ in range(threads_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert len(seen) == threads_count, "each thread should have recorded a client"
    assert len({id(c) for c in seen}) == threads_count, "clients must not be shared across threads"
    assert len(created) == threads_count, "exactly one connection per thread"
