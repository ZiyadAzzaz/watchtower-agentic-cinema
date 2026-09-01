"""Defense-in-depth middleware loaded by the official mcp-clickhouse process."""

from __future__ import annotations

import re

from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from mcp.types import CallToolRequest

_FORBIDDEN = re.compile(
    r"\b(ALTER|ATTACH|CREATE|DELETE|DETACH|DROP|GRANT|INSERT|KILL|OPTIMIZE|RENAME|REPLACE|REVOKE|SYSTEM|TRUNCATE|UPDATE)\b",
    re.IGNORECASE,
)
_APPROVED_TABLES = re.compile(r"\bwatchtower\.(telemetry_events|titles|incidents)\b", re.I)


class WatchtowerReadOnlyGuard(Middleware):
    async def on_call_tool(
        self,
        context: MiddlewareContext[CallToolRequest],
        call_next: CallNext,
    ):
        message = context.message
        if getattr(message, "name", "") != "run_query":
            return await call_next(context)
        arguments = getattr(message, "arguments", None) or {}
        query = str(arguments.get("query", "")).strip()
        normalized = query.rstrip(";").strip()
        if not normalized.upper().startswith(("SELECT", "WITH")):
            raise ValueError("WatchTower MCP permits SELECT/WITH analytics queries only.")
        if ";" in normalized or "--" in normalized or "/*" in normalized:
            raise ValueError("Multiple statements and SQL comments are not permitted.")
        if _FORBIDDEN.search(normalized):
            raise ValueError("A forbidden SQL operation was blocked by WatchTower MCP guard.")
        if not _APPROVED_TABLES.search(normalized):
            raise ValueError("Query must target a WatchTower allowlisted table.")
        if not re.search(r"\bLIMIT\s+\d+\b", normalized, re.IGNORECASE):
            raise ValueError("All MCP analytics queries must include an explicit LIMIT.")
        return await call_next(context)


def setup_middleware(mcp) -> None:
    mcp.add_middleware(WatchtowerReadOnlyGuard())
