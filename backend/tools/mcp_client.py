"""Minimal, bounded stdio MCP client shared by the Cua adapter and external MCP servers.

One call opens one stdio session, runs a short sequence of tool calls in it,
and closes it. Sessions are never kept open between model turns: that keeps
process lifetime obvious (no orphaned drivers) at the cost of a process spawn
per action, which is small next to a model round-trip.

This module performs no policy decisions. Callers decide which tools may be
listed or invoked; this module only normalizes transport results and errors.
"""
from __future__ import annotations

import asyncio
import base64
import os
from dataclasses import dataclass, field
from typing import Any

# Never hand provider/API secrets to an external tool process unless the
# server configuration explicitly passes a variable through.
_SECRET_MARKERS = ("KEY", "SECRET", "TOKEN", "PASSWORD", "DATABASE_URL", "CREDENTIAL")


def scrubbed_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The parent environment minus anything that looks like a credential."""
    env = {
        name: value for name, value in os.environ.items()
        if not any(marker in name.upper() for marker in _SECRET_MARKERS)
    }
    env.update(extra or {})
    return env


@dataclass(frozen=True)
class StdioServer:
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None


def _imports():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    return ClientSession, StdioServerParameters, stdio_client


def tool_schema(tool: Any) -> dict[str, Any]:
    if isinstance(tool, dict):
        return tool
    if hasattr(tool, "model_dump"):
        return tool.model_dump(by_alias=True)
    if hasattr(tool, "dict"):
        return tool.dict(by_alias=True)
    raise TypeError("MCP server returned an unsupported tool schema.")


def normalize_call_result(result: Any) -> dict[str, Any]:
    """Convert an MCP CallToolResult into plain JSON-safe data."""
    blocks: list[dict[str, Any]] = []
    for item in getattr(result, "content", None) or []:
        item_type = getattr(item, "type", None)
        if item_type == "image":
            data = getattr(item, "data", b"")
            if isinstance(data, bytes):
                data = base64.b64encode(data).decode("ascii")
            blocks.append({
                "type": "image",
                "mime_type": getattr(item, "mimeType", "image/png"),
                "data_base64": str(data),
            })
        else:
            blocks.append({"type": str(item_type or "text"), "text": str(getattr(item, "text", ""))})
    return {
        "is_error": bool(getattr(result, "isError", False)),
        "structured_content": getattr(result, "structuredContent", None),
        "content": blocks,
    }


async def _session(server: StdioServer, calls: list[tuple[str, dict[str, Any]]], list_tools: bool):
    ClientSession, StdioServerParameters, stdio_client = _imports()
    params = StdioServerParameters(
        command=server.command, args=list(server.args),
        env=server.env if server.env is not None else scrubbed_environment(),
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = None
            if list_tools:
                listed = await session.list_tools()
                tools = [tool_schema(item) for item in listed.tools]
            results = []
            for name, arguments in calls:
                results.append(normalize_call_result(await session.call_tool(name, arguments)))
            return tools, results


def run_session(
    server: StdioServer,
    calls: list[tuple[str, dict[str, Any]]] | None = None,
    *,
    list_tools: bool = False,
    timeout_seconds: float = 30,
) -> tuple[list[dict[str, Any]] | None, list[dict[str, Any]]]:
    """Open one bounded session, optionally list tools, run calls in order.

    Raises TimeoutError, OSError, or the MCP library's exception on transport
    failure; callers convert those into structured tool results. Must not be
    called from a running event loop (Xelora tasks run in worker threads).
    """
    return asyncio.run(asyncio.wait_for(
        _session(server, list(calls or []), list_tools), timeout=timeout_seconds,
    ))


def describe_error(exc: BaseException) -> str:
    """A short, user-meaningful transport error without a traceback."""
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return "The MCP server did not respond before the timeout."
    if isinstance(exc, FileNotFoundError):
        return f"MCP server executable was not found: {exc}"
    if isinstance(exc, BaseExceptionGroup):
        inner = exc.exceptions[0] if exc.exceptions else exc
        return describe_error(inner) if inner is not exc else f"{type(exc).__name__}: {exc}"
    return f"{type(exc).__name__}: {exc}"[:500]
