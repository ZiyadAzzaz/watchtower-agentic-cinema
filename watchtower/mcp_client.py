from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import Sequence
from contextlib import AsyncExitStack, suppress
from typing import Any, Protocol

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from watchtower.config import Settings

_QueryRequest = tuple[str, "asyncio.Future[Any]"]


class QueryExecutor(Protocol):
    async def query(self, sql: str) -> list[dict[str, Any]]: ...


class OfficialClickHouseMcpClient:
    """Executes allowlisted analytics through ClickHouse's official MCP server."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._requests: asyncio.Queue[_QueryRequest | None] | None = None
        self._worker: asyncio.Task[None] | None = None
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
        requests = await self._ensure_worker()
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        await requests.put((sql, future))
        response = await future
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

    async def _ensure_worker(self) -> asyncio.Queue[_QueryRequest | None]:
        async with self._lock:
            if self._worker is not None and not self._worker.done():
                assert self._requests is not None
                return self._requests
            requests: asyncio.Queue[_QueryRequest | None] = asyncio.Queue()
            started: asyncio.Future[None] = asyncio.get_running_loop().create_future()
            worker = asyncio.create_task(self._serve(requests, started))
            try:
                await started
            except BaseException:
                worker.cancel()
                with suppress(asyncio.CancelledError):
                    await worker
                raise
            self._requests = requests
            self._worker = worker
            return requests

    async def _serve(
        self,
        requests: asyncio.Queue[_QueryRequest | None],
        started: asyncio.Future[None],
    ) -> None:
        """Own the stdio session for its whole lifetime.

        The MCP stdio client opens an anyio task group, which may only be
        entered and exited by one task. Serving every query from this single
        task keeps that contract while still serialising access to the server.
        """
        server = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_clickhouse.main"],
            env=self._environment(),
        )
        try:
            async with AsyncExitStack() as stack:
                read_stream, write_stream = await stack.enter_async_context(stdio_client(server))
                session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
                await session.initialize()
                if not started.done():
                    started.set_result(None)
                while True:
                    item = await requests.get()
                    if item is None:
                        return
                    sql, future = item
                    try:
                        result = await session.call_tool("run_query", {"query": sql})
                    except BaseException as exc:
                        if not future.done():
                            future.set_exception(exc)
                        raise
                    if not future.done():
                        future.set_result(result)
        except BaseException as exc:
            if not started.done():
                started.set_exception(exc)
            raise
        finally:
            self._drain(requests)

    @staticmethod
    def _drain(requests: asyncio.Queue[_QueryRequest | None]) -> None:
        while True:
            try:
                item = requests.get_nowait()
            except asyncio.QueueEmpty:
                return
            if item is not None and not item[1].done():
                item[1].set_exception(RuntimeError("mcp-clickhouse session closed"))

    async def close(self) -> None:
        async with self._lock:
            worker, requests = self._worker, self._requests
            self._worker = None
            self._requests = None
        if worker is None:
            return
        if requests is not None:
            await requests.put(None)
        with suppress(asyncio.CancelledError, Exception):
            await asyncio.wait_for(worker, timeout=10)
        if not worker.done():
            worker.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await worker

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
