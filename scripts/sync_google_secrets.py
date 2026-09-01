"""Synchronize WatchTower runtime secrets to the fixed Google Cloud project."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from google.api_core.exceptions import NotFound
from google.cloud import secretmanager

from watchtower.config import WATCHTOWER_PROJECT_ID, Settings


def replace_env_value(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    output: list[str] = []
    found = False
    for line in lines:
        candidate, separator, _ = line.partition("=")
        if separator and candidate == key:
            output.append(f"{key}={value}")
            found = True
        else:
            output.append(line)
    if not found:
        output.append(f"{key}={value}")
    temporary = path.with_suffix(".env.tmp")
    temporary.write_text("\n".join(output) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    env_path = Path(".env")
    settings = Settings()
    if settings.google_cloud_project != WATCHTOWER_PROJECT_ID:
        raise RuntimeError("Refusing to synchronize secrets outside the WatchTower project.")
    if settings.clickhouse_user != "watchtower_app":
        raise RuntimeError("Scoped ClickHouse application credentials are required.")
    if settings.clickhouse_mcp_user != "watchtower_mcp":
        raise RuntimeError("Scoped ClickHouse MCP credentials are required.")

    admin_token = (
        settings.watchtower_admin_token.get_secret_value()
        if settings.watchtower_admin_token
        else ""
    )
    if admin_token in {"", "local-demo-only", "replace-with-a-random-secret"}:
        admin_token = f"{secrets.token_urlsafe(48)}!Aa1"
        replace_env_value(env_path, "WATCHTOWER_ADMIN_TOKEN", admin_token)

    values = {
        "watchtower-clickhouse-app-password": (settings.clickhouse_password.get_secret_value()),
        "watchtower-clickhouse-mcp-password": (settings.clickhouse_mcp_password.get_secret_value()),
        "watchtower-admin-token": admin_token,
    }
    if any(not value or value.startswith(("REPLACE_", "change-me")) for value in values.values()):
        raise RuntimeError("A required runtime secret is missing or still a placeholder.")

    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{WATCHTOWER_PROJECT_ID}"
    for secret_id, value in values.items():
        name = f"{parent}/secrets/{secret_id}"
        try:
            client.get_secret(request={"name": name})
        except NotFound:
            client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": secret_id,
                    "secret": {"replication": {"automatic": {}}},
                }
            )
        client.add_secret_version(
            request={"parent": name, "payload": {"data": value.encode("utf-8")}}
        )
        print(f"Secret synchronized: {secret_id}")
    print(f"Secret target project: {WATCHTOWER_PROJECT_ID}")
    print("No secret value was displayed.")


if __name__ == "__main__":
    main()
