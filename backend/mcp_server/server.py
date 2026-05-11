"""
mcp_server/server.py
MCP Support, the buildable half: this exposes every skill in
skills/registry.py as a real MCP server, so any MCP-compatible client
(Claude Desktop, another MCP-aware agent, etc.) can connect to and use
YOUR Excel skills directly - no bespoke integration code needed on
either side, which is exactly what MCP is for.

The other half of "MCP Support" - THIS agent calling OUT to external
MCP servers (a company's database server, a ticketing system, etc.) -
is a separate, smaller piece of work once you have a specific external
server to point at; it isn't built here since there's nothing concrete
to test it against yet. Extending providers.py's tool list with tools
discovered from an external MCP server is the natural next step for that.

Run standalone with:
    python -m mcp_server.server
Then point an MCP client (e.g. Claude Desktop's config) at this process
over stdio, per the MCP client's own setup instructions.
"""

import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

import skills  # noqa: F401 - triggers skill registration
from skills.base import SKILL_REGISTRY
from skills.registry import run_skill
from skills.excel_shared import bind_workbook_context

app = Server("ai-excel-agent")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name=name, description=entry["description"], inputSchema=entry["input_schema"])
        for name, entry in SKILL_REGISTRY.items()
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name not in SKILL_REGISTRY:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown skill '{name}'"}))]

    # No task/workbook context here (an external MCP client isn't running
    # through agent/core.py's task loop) - default to "whichever Excel
    # workbook is currently active", same as single-task usage.
    bind_workbook_context(None)

    try:
        result = run_skill(name, **arguments)
    except Exception as e:
        result = {"error": str(e), "verified": False}

    return [TextContent(type="text", text=json.dumps(result, default=str))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
