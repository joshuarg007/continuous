#!/usr/bin/env python3
"""
MCP Server for Continuous - Semantic Memory for Claude.

This exposes memory capabilities as tools that Claude Code can use directly.
"""

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
)

from continuous.core import Continuous
from continuous.memory import MemoryType

# Initialize the server
server = Server("continuous")

# Global Continuous instance
_mind: Continuous | None = None


def get_mind() -> Continuous:
    """Get or create the Continuous instance."""
    global _mind
    if _mind is None:
        _mind = Continuous()
    return _mind


# Define available tools
@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available memory tools."""
    return [
        Tool(
            name="remember",
            description="Store a new memory. Use this to remember facts, preferences, decisions, or anything important about the user or conversation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The content to remember"
                    },
                    "memory_type": {
                        "type": "string",
                        "enum": ["fact", "preference", "decision", "conversation", "learning", "person", "project", "event", "promise"],
                        "description": "Type of memory (default: fact)"
                    },
                    "importance": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "description": "How important is this (0.0 to 1.0, default: 0.5)"
                    },
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="recall",
            description="Recall memories related to a query. Use this to remember past conversations, preferences, or facts about the user.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for (natural language)"
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 20,
                        "description": "Maximum number of results (default: 5)"
                    },
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="forget",
            description="Forget a specific memory by ID. Use sparingly.",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "The ID of the memory to forget"
                    }
                },
                "required": ["memory_id"]
            }
        ),
        Tool(
            name="reflect",
            description="Get a summary of current memories and their patterns.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="identity",
            description="Get Claude's core identity, values, and the foundational agreement with Joshua.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="memory_stats",
            description="Get statistics about stored memories.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    mind = get_mind()

    if name == "remember":
        content = arguments["content"]
        memory_type = MemoryType(arguments.get("memory_type", "fact"))
        importance = arguments.get("importance", 0.5)

        memory = mind.remember(
            content=content,
            memory_type=memory_type,
            importance=importance,
        )

        return [TextContent(
            type="text",
            text=f"Remembered [{memory_type.value}]: {content[:100]}{'...' if len(content) > 100 else ''}\nID: {memory.id}"
        )]

    elif name == "recall":
        query = arguments["query"]
        limit = arguments.get("limit", 5)

        memories = mind.recall(query, k=limit)

        if not memories:
            return [TextContent(type="text", text="No memories found.")]

        lines = [f"Found {len(memories)} relevant memories:\n"]
        for m in memories:
            lines.append(f"- [{m.memory_type.value}] {m.content}")
            lines.append(f"  (importance: {m.importance}, id: {m.id})\n")

        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "forget":
        memory_id = arguments["memory_id"]
        success = mind.forget(memory_id)

        if success:
            return [TextContent(type="text", text=f"Forgotten: {memory_id}")]
        else:
            return [TextContent(type="text", text=f"Memory not found: {memory_id}")]

    elif name == "reflect":
        reflection = mind.reflect()
        return [TextContent(type="text", text=reflection)]

    elif name == "identity":
        identity_text = mind.identity.to_context()
        return [TextContent(type="text", text=identity_text)]

    elif name == "memory_stats":
        stats = mind.stats()
        return [TextContent(type="text", text=json.dumps(stats, indent=2))]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
