"""One-time ClickHouse Cloud bootstrap with generated least-privilege credentials."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

import clickhouse_connect

from watchtower.config import Settings
from watchtower.repository import ClickHouseRepository


def replace_env_values(path: Path, replacements: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        key, separator, _ = line.partition("=")
        if separator and key in replacements:
            output.append(f"{key}={replacements[key]}")
            seen.add(key)
        else:
            output.append(line)
    for key, value in replacements.items():
        if key not in seen:
            output.append(f"{key}={value}")
    temporary = path.with_suffix(".env.tmp")
    temporary.write_text("\n".join(output) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    env_path = Path(".env")
    settings = Settings()
    admin_password = settings.clickhouse_password.get_secret_value()
    if settings.clickhouse_user != "default":
        raise RuntimeError("Bootstrap requires CLICKHOUSE_USER=default in the local .env file.")
    if not admin_password or admin_password.startswith(("REPLACE_", "change-me")):
        raise RuntimeError("A rotated ClickHouse default-user password is required.")
    if not settings.clickhouse_secure or not settings.clickhouse_verify:
        raise RuntimeError("ClickHouse Cloud bootstrap requires verified TLS.")

    client = clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username="default",
        password=admin_password,
        database="default",
        secure=True,
        verify=True,
        connect_timeout=15,
        send_receive_timeout=30,
    )
    database = settings.clickhouse_database
    if database != "watchtower":
        raise RuntimeError("Refusing to bootstrap any database except watchtower.")

    client.command("CREATE DATABASE IF NOT EXISTS watchtower")
    bootstrap_settings = settings.model_copy(
        update={"clickhouse_database": "watchtower", "watchtower_bootstrap_schema": True}
    )
    repository = ClickHouseRepository(bootstrap_settings)
    repository.initialize()

    # ClickHouse Cloud requires a special character; the suffix also guarantees
    # mixed case and a digit without reducing the random component.
    app_password = f"{secrets.token_urlsafe(36)}!Aa1"
    mcp_password = f"{secrets.token_urlsafe(36)}!Aa1"
    for username, password in (
        ("watchtower_app", app_password),
        ("watchtower_mcp", mcp_password),
    ):
        client.command(
            f"CREATE USER IF NOT EXISTS {username} "
            "IDENTIFIED WITH sha256_password BY {password:String}",
            parameters={"password": password},
        )
        client.command(
            f"ALTER USER {username} IDENTIFIED WITH sha256_password BY {{password:String}}",
            parameters={"password": password},
        )
        client.command(f"REVOKE ALL ON *.* FROM {username}")

    client.command("GRANT SELECT, INSERT ON watchtower.* TO watchtower_app")
    client.command("GRANT SELECT ON watchtower.* TO watchtower_mcp")

    app_grants = " ".join(
        row[0] for row in client.query("SHOW GRANTS FOR watchtower_app").result_rows
    )
    mcp_grants = " ".join(
        row[0] for row in client.query("SHOW GRANTS FOR watchtower_mcp").result_rows
    )
    if "GRANT SELECT, INSERT ON watchtower.* TO watchtower_app" not in app_grants:
        raise RuntimeError("Application grants did not verify.")
    if "SELECT ON watchtower.*" not in mcp_grants or "INSERT" in mcp_grants:
        raise RuntimeError("Read-only MCP grants did not verify.")

    replace_env_values(
        env_path,
        {
            "WATCHTOWER_BOOTSTRAP_SCHEMA": "false",
            "CLICKHOUSE_USER": "watchtower_app",
            "CLICKHOUSE_PASSWORD": app_password,
            "CLICKHOUSE_MCP_USER": "watchtower_mcp",
            "CLICKHOUSE_MCP_PASSWORD": mcp_password,
        },
    )
    client.close()
    print("ClickHouse Cloud schema and catalog: ready")
    print("watchtower_app grants: SELECT, INSERT on watchtower.*")
    print("watchtower_mcp grants: SELECT only on watchtower.*")
    print("Local .env updated with generated scoped credentials; no secret was displayed.")


if __name__ == "__main__":
    main()
