from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

WATCHTOWER_PROJECT_ID = "watchtower-507216"


class Settings(BaseSettings):
    """Runtime configuration with explicit production safety checks."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    google_cloud_project: str = WATCHTOWER_PROJECT_ID
    google_cloud_location: str = "us-central1"
    google_genai_use_vertexai: bool = True
    watchtower_env: Literal["development", "test", "production"] = "development"
    watchtower_agent_model: str = "gemini-2.5-flash"
    watchtower_detection_interval_seconds: int = Field(default=15, ge=5, le=300)
    watchtower_lookback_minutes: int = Field(default=5, ge=2, le=15)
    watchtower_baseline_minutes: int = Field(default=60, ge=20, le=360)
    watchtower_mcp_timeout_seconds: int = Field(default=30, ge=5, le=120)
    watchtower_bootstrap_schema: bool = True
    watchtower_admin_token: SecretStr | None = None
    # Published in the README so judges can drive the full decision loop. It is
    # deliberately separate from the operator token, which stays in Secret
    # Manager, and every request it authorises is rate limited.
    watchtower_demo_token: SecretStr | None = None
    watchtower_demo_rate_limit: int = Field(default=10, ge=1, le=100)
    watchtower_demo_rate_window_seconds: int = Field(default=600, ge=30, le=3600)

    clickhouse_host: str = "localhost"
    clickhouse_port: int = Field(default=8123, ge=1, le=65535)
    clickhouse_database: str = "watchtower"
    clickhouse_user: str = "watchtower_app"
    clickhouse_password: SecretStr = SecretStr("change-me")
    clickhouse_secure: bool = False
    clickhouse_verify: bool = False
    clickhouse_mcp_user: str = "watchtower_mcp"
    clickhouse_mcp_password: SecretStr = SecretStr("change-me-too")

    @model_validator(mode="after")
    def enforce_production_safety(self) -> Settings:
        if self.watchtower_env == "production":
            if self.google_cloud_project != WATCHTOWER_PROJECT_ID:
                raise ValueError(
                    f"Production is locked to {WATCHTOWER_PROJECT_ID}; "
                    f"received {self.google_cloud_project!r}."
                )
            if not self.google_genai_use_vertexai:
                raise ValueError("Production must use Gemini through Vertex AI.")
            if self.watchtower_admin_token is None:
                raise ValueError("WATCHTOWER_ADMIN_TOKEN is required in production.")
            demo = self.watchtower_demo_token
            if demo is not None:
                if demo.get_secret_value() == self.watchtower_admin_token.get_secret_value():
                    raise ValueError("The demo token must differ from the operator token.")
                if len(demo.get_secret_value()) < 8:
                    raise ValueError("The demo token must be at least 8 characters.")
            if self.watchtower_bootstrap_schema:
                raise ValueError("Production runtime identity must not bootstrap database schema.")
            if not self.clickhouse_secure or not self.clickhouse_verify:
                raise ValueError("Production ClickHouse connections must use verified TLS.")
            insecure_values = {"change-me", "change-me-too", ""}
            if self.clickhouse_password.get_secret_value() in insecure_values:
                raise ValueError("A real ClickHouse ingestion credential is required.")
            if self.clickhouse_mcp_password.get_secret_value() in insecure_values:
                raise ValueError("A real read-only MCP credential is required.")
        return self

    @property
    def is_production(self) -> bool:
        return self.watchtower_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
