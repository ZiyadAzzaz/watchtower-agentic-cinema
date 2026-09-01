import pytest
from pydantic import ValidationError

from watchtower.config import WATCHTOWER_PROJECT_ID, Settings


def test_production_is_locked_to_watchtower_project() -> None:
    with pytest.raises(ValidationError, match=WATCHTOWER_PROJECT_ID):
        Settings(
            _env_file=None,
            watchtower_env="production",
            google_cloud_project="wrong-project-123",
            watchtower_admin_token="secret",
            clickhouse_secure=True,
            clickhouse_verify=True,
            clickhouse_password="real-app-secret",
            clickhouse_mcp_password="real-mcp-secret",
            watchtower_bootstrap_schema=False,
        )


def test_production_requires_vertex_tls_secret_and_no_bootstrap() -> None:
    with pytest.raises(ValidationError):
        Settings(watchtower_env="production", _env_file=None)


def test_test_environment_accepts_local_clickhouse() -> None:
    settings = Settings(watchtower_env="test", _env_file=None)
    assert settings.google_cloud_project == WATCHTOWER_PROJECT_ID
    assert not settings.is_production
