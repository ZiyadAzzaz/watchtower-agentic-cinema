"""The published demo key lets judges drive the loop without opening a hole."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from watchtower.api import _token_matches, create_app
from watchtower.config import Settings
from watchtower.ratelimit import SlidingWindowLimiter

OPERATOR = "operator-token-value"
DEMO = "watchtower-judge-demo"


def settings(**overrides) -> Settings:
    base = dict(
        watchtower_env="production",
        watchtower_bootstrap_schema=False,
        watchtower_admin_token=OPERATOR,
        watchtower_demo_token=DEMO,
        clickhouse_password="test-app-password",
        clickhouse_mcp_password="test-mcp-password",
        clickhouse_secure=True,
        clickhouse_verify=True,
        _env_file=None,
    )
    base.update(overrides)
    return Settings(**base)


def client_for(**overrides) -> TestClient:
    resolved = settings(**overrides)

    class Runtime:
        settings = resolved

        async def initialize(self) -> None:
            return None

        async def close(self) -> None:
            return None

        async def tick_if_due(self, force: bool = False) -> list:
            return []

        async def decide(self, incident_id, status, note):
            return None

    return TestClient(create_app(Runtime()))


def tick(client: TestClient, token: str | None):
    headers = {"X-Watchtower-Token": token} if token else {}
    return client.post("/api/admin/tick", json={}, headers=headers)


# --- the limiter itself ------------------------------------------------------


def test_limiter_allows_up_to_the_limit_then_refuses() -> None:
    limiter = SlidingWindowLimiter(limit=3, window_seconds=60)
    assert [limiter.try_acquire(now=0.0) for _ in range(3)] == [True, True, True]
    assert limiter.try_acquire(now=0.0) is False
    assert limiter.remaining(now=0.0) == 0
    assert limiter.retry_after_seconds(now=0.0) >= 1


def test_limiter_frees_capacity_once_the_window_slides() -> None:
    limiter = SlidingWindowLimiter(limit=2, window_seconds=60)
    assert limiter.try_acquire(now=0.0) is True
    assert limiter.try_acquire(now=10.0) is True
    assert limiter.try_acquire(now=20.0) is False
    # The first hit ages out at t=60.
    assert limiter.try_acquire(now=61.0) is True


@pytest.mark.parametrize(("limit", "window"), [(0, 60), (1, 0)])
def test_limiter_rejects_nonsense_configuration(limit: int, window: int) -> None:
    with pytest.raises(ValueError):
        SlidingWindowLimiter(limit=limit, window_seconds=window)


# --- how the API uses it -----------------------------------------------------


def test_operator_token_is_accepted_and_never_rate_limited() -> None:
    with client_for(watchtower_demo_rate_limit=1) as client:
        for _ in range(5):
            assert tick(client, OPERATOR).status_code == 200


def test_demo_key_is_accepted() -> None:
    with client_for() as client:
        assert tick(client, DEMO).status_code == 200


def test_demo_key_is_rate_limited_and_says_so() -> None:
    with client_for(
        watchtower_demo_rate_limit=2, watchtower_demo_rate_window_seconds=600
    ) as client:
        assert tick(client, DEMO).status_code == 200
        assert tick(client, DEMO).status_code == 200
        blocked = tick(client, DEMO)
        assert blocked.status_code == 429
        assert "limits how often" in blocked.json()["detail"]
        assert int(blocked.headers["Retry-After"]) >= 1


def test_rate_limiting_the_demo_key_never_blocks_the_operator() -> None:
    with client_for(watchtower_demo_rate_limit=1) as client:
        assert tick(client, DEMO).status_code == 200
        assert tick(client, DEMO).status_code == 429
        # The owner must still be able to run the demo.
        assert tick(client, OPERATOR).status_code == 200


@pytest.mark.parametrize("token", [None, "", "wrong-token", "watchtower-judge-dem"])
def test_everything_else_is_still_rejected(token: str | None) -> None:
    with client_for() as client:
        assert tick(client, token).status_code == 401


def test_demo_token_may_not_equal_the_operator_token() -> None:
    with pytest.raises(ValueError, match="must differ"):
        settings(watchtower_demo_token=OPERATOR)


def test_demo_token_must_not_be_trivially_short() -> None:
    with pytest.raises(ValueError, match="at least 8"):
        settings(watchtower_demo_token="short")


def test_no_demo_token_means_no_demo_access() -> None:
    with client_for(watchtower_demo_token=None) as client:
        assert tick(client, DEMO).status_code == 401
        assert tick(client, OPERATOR).status_code == 200


@pytest.mark.parametrize(
    ("configured", "presented"),
    [
        ("﻿watchtower-judge-demo", "watchtower-judge-demo"),
        ("watchtower-judge-demo", "﻿watchtower-judge-demo"),
        ("ünicode-token", "unicode-token"),
        ("日本語", "日本語"),
    ],
)
def test_token_comparison_tolerates_non_ascii(configured: str, presented: str) -> None:
    """hmac.compare_digest raises TypeError on a str holding non-ASCII.

    A secret written by a tool that adds a BOM once made every control request
    return 500 instead of 401.
    """
    result = _token_matches(configured, presented)
    assert result is (configured == presented)


def test_a_non_ascii_configured_secret_still_rejects_cleanly() -> None:
    with client_for(watchtower_demo_token="﻿watchtower-judge-demo") as client:
        # Wrong key: a clean 401, never a server error.
        assert tick(client, DEMO).status_code == 401
        # The operator path is unaffected.
        assert tick(client, OPERATOR).status_code == 200


def decide(client: TestClient, token: str | None):
    headers = {"X-Watchtower-Token": token} if token else {}
    return client.post(
        "/api/incidents/00000000-0000-0000-0000-000000000000/approve",
        json={"note": "ok"},
        headers=headers,
    )


def test_recording_a_decision_is_never_rate_limited() -> None:
    """A judge who triggers incidents must still be able to approve one."""
    with client_for(watchtower_demo_rate_limit=1) as client:
        assert tick(client, DEMO).status_code == 200
        assert tick(client, DEMO).status_code == 429, "investigations are metered"
        # Deciding costs nothing and invokes no model, so it stays open.
        for _ in range(5):
            assert decide(client, DEMO).status_code != 429


def test_a_decision_still_needs_a_valid_key() -> None:
    with client_for() as client:
        assert decide(client, None).status_code == 401
        assert decide(client, "wrong").status_code == 401


def test_a_long_window_bounds_the_published_key_per_process() -> None:
    """A published key is discoverable, so each process has a longer allowance."""
    with client_for(
        watchtower_demo_rate_limit=100,
        watchtower_demo_rate_window_seconds=600,
        watchtower_demo_daily_limit=3,
    ) as client:
        for _ in range(3):
            assert tick(client, DEMO).status_code == 200
        blocked = tick(client, DEMO)
        assert blocked.status_code == 429
        assert "per-instance 24-hour limit" in blocked.json()["detail"]


def test_the_daily_ceiling_never_applies_to_the_operator() -> None:
    with client_for(watchtower_demo_daily_limit=1) as client:
        assert tick(client, DEMO).status_code == 200
        assert tick(client, DEMO).status_code == 429
        for _ in range(4):
            assert tick(client, OPERATOR).status_code == 200


def test_the_daily_ceiling_never_blocks_a_decision() -> None:
    """A judge must always be able to finish the loop they started."""
    with client_for(watchtower_demo_daily_limit=1) as client:
        assert tick(client, DEMO).status_code == 200
        assert tick(client, DEMO).status_code == 429
        for _ in range(4):
            assert decide(client, DEMO).status_code != 429
