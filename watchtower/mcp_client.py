from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import Sequence
from contextlib import AsyncExitStack
from typing import Any, Protocol

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from watchtower.config import Settings


class QueryExecutor(Protocol):
    async def query(self, sql: str) -> list[dict[str, Any]]: ...


class OfficialClickHouseMcpClient:
    """Executes allowlisted analytics through ClickHouse's official MCP server."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._lock = asyncio.Lock()

    def _environment(self) -> dict[str, str]:
        env = dict(os.environ)
        env.update(
            {
                "CLICKHOUSE_HOST": self.settings.clickhouse_host,
                "CLICKHOUSE_PORT": str(self.settings.clickhouse_port),
                "CLICKHOUSE_DATABASE": self.settings.clickhouse_database,
                "CLICKHOUSE_USER": self.settings.clickhouse_mcp_user,
                "CLICKHOUSE_PASSWORD": self.settings.clickhouse_mcp_password.get_secret_value(),
                "CLICKHOUSE_SECURE": str(self.settings.clickhouse_secure).lower(),
                "CLICKHOUSE_VERIFY": str(self.settings.clickhouse_verify).lower(),
                "CLICKHOUSE_ALLOW_WRITE_ACCESS": "false",
                "CLICKHOUSE_ALLOW_DROP": "false",
                "CLICKHOUSE_MCP_SERVER_TRANSPORT": "stdio",
                "CLICKHOUSE_MCP_QUERY_TIMEOUT": str(self.settings.watchtower_mcp_timeout_seconds),
                "CLICKHOUSE_MCP_MAX_RESULT_ROWS": "500",
                "MCP_MIDDLEWARE_MODULE": "watchtower.mcp_guard",
                "FASTMCP_CHECK_FOR_UPDATES": "off",
            }
        )
        return env

    async def query(self, sql: str) -> list[dict[str, Any]]:
        async with self._lock:
            session = await self._get_session()
            response = await session.call_tool("run_query", {"query": sql})
        if response.isError:
            text = self._text_content(response.content)
            raise RuntimeError(f"mcp-clickhouse rejected the analytics query: {text}")
        text_result = self._text_content(response.content)
        if text_result.strip():
            return self._parse_text(text_result)
        structured = getattr(response, "structuredContent", None)
        if structured:
            return self._coerce_rows(structured)
        return []

    async def _get_session(self) -> ClientSession:
        if self._session is not None:
            return self._session
        server = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_clickhouse.main"],
            env=self._environment(),
        )
        stack = AsyncExitStack()
        try:
            read_stream, write_stream = await stack.enter_async_context(stdio_client(server))
            session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
            await session.initialize()
        except BaseException:
            await stack.aclose()
            raise
        self._stack = stack
        self._session = session
        return session

    async def close(self) -> None:
        async with self._lock:
            if self._stack is not None:
                await self._stack.aclose()
            self._stack = None
            self._session = None

    @staticmethod
    def _text_content(content: Sequence[Any]) -> str:
        return "\n".join(str(item.text) for item in content if hasattr(item, "text"))

    @classmethod
    def _parse_text(cls, value: str) -> list[dict[str, Any]]:
        if not value.strip():
            return []
        try:
            return cls._coerce_rows(json.loads(value))
        except json.JSONDecodeError as exc:
            raise RuntimeError("mcp-clickhouse returned non-JSON output") from exc

    @staticmethod
    def _coerce_rows(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, dict):
            if isinstance(value.get("result"), str):
                return OfficialClickHouseMcpClient._parse_text(value["result"])
            columns = value.get("columns")
            positional_rows = value.get("rows")
            if isinstance(columns, list) and isinstance(positional_rows, list):
                return [
                    dict(zip(columns, row, strict=False))
                    for row in positional_rows
                    if isinstance(row, list | tuple)
                ]
            for key in ("rows", "data", "result"):
                if isinstance(value.get(key), list):
                    value = value[key]
                    break
            else:
                value = [value]
        if not isinstance(value, list):
            raise RuntimeError("mcp-clickhouse result did not contain a row list")
        return [dict(row) for row in value if isinstance(row, dict)]


class StaticQueryExecutor:
    """Test-only MCP substitute; never selected by production configuration."""

    def __init__(self, responses: list[list[dict[str, Any]]]):
        self.responses = list(responses)
        self.queries: list[str] = []

    async def query(self, sql: str) -> list[dict[str, Any]]:
        self.queries.append(sql)
        return self.responses.pop(0) if self.responses else []
