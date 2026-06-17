"""
SOTI MobiControl MCP Server
Exposes SOTI MobiControl REST APIs as MCP tools.
"""

import asyncio
import json
import logging
from typing import Any

from dotenv import load_dotenv
load_dotenv()   # Must be called before soti_client imports os.getenv() values

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

from soti_client import SotiClient
from tools import TOOL_DEFINITIONS, TOOL_HANDLERS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP server
app = Server("soti-mobicontrol")

# Initialize SOTI client (credentials loaded from config/env)
soti_client = SotiClient()


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    """Return all available SOTI MobiControl tools."""
    return TOOL_DEFINITIONS


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Dispatch tool calls to the appropriate handler."""
    if name not in TOOL_HANDLERS:
        raise ValueError(f"Unknown tool: {name}")

    handler = TOOL_HANDLERS[name]
    try:
        result = await handler(soti_client, arguments)
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        logger.error(f"Tool '{name}' failed: {e}", exc_info=True)
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": str(e), "tool": name}),
            )
        ]


async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        logger.info("SOTI MobiControl MCP Server started")
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
