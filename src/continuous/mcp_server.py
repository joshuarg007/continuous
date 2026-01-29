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
from continuous.consolidation import MemoryConsolidator, ContradictionDetector, ProjectScope

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
        Tool(
            name="briefing",
            description="Get a contextual briefing with high-importance memories, recent context, and relevant memories for a topic. Use at session start or when switching contexts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Optional topic to focus the briefing on"
                    }
                }
            }
        ),
        Tool(
            name="link_memories",
            description="Find and create links between related memories. Call this after storing important memories to build the knowledge graph.",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "ID of memory to find links for"
                    },
                    "threshold": {
                        "type": "number",
                        "minimum": 0.5,
                        "maximum": 1.0,
                        "description": "Similarity threshold for linking (default: 0.75)"
                    }
                },
                "required": ["memory_id"]
            }
        ),
        Tool(
            name="boost_memory",
            description="Increase the importance of a memory that proved useful. Call this when a recalled memory was helpful.",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "ID of memory to boost"
                    }
                },
                "required": ["memory_id"]
            }
        ),
        Tool(
            name="memory_graph",
            description="Get the relationship graph around a memory - what it's connected to.",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "ID of memory to explore connections from"
                    },
                    "depth": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 3,
                        "description": "How many levels of connections to traverse (default: 2)"
                    }
                },
                "required": ["memory_id"]
            }
        ),
        Tool(
            name="check_contradiction",
            description="Check if new content contradicts existing memories before storing. Use for preferences, decisions, and facts that might conflict with existing knowledge.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The content to check for contradictions"
                    },
                    "memory_type": {
                        "type": "string",
                        "enum": ["preference", "decision", "fact"],
                        "description": "Type of memory to check against"
                    }
                },
                "required": ["content", "memory_type"]
            }
        ),
        Tool(
            name="project_recall",
            description="Recall memories with boost for current project context. Memories tagged with the current project rank higher.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for"
                    },
                    "project": {
                        "type": "string",
                        "description": "Current project name (e.g., 'continuous', 'made4founders')"
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 20,
                        "description": "Maximum results (default: 5)"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="tag_project",
            description="Tag a memory with a project name for better project-scoped recall.",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "ID of memory to tag"
                    },
                    "project": {
                        "type": "string",
                        "description": "Project name to tag with"
                    }
                },
                "required": ["memory_id", "project"]
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

    elif name == "briefing":
        topic = arguments.get("topic")
        lines = [
            "# Memory Briefing",
            "",
            mind.identity.to_context(),
            "",
            "---",
            "",
        ]

        # High-importance memories
        all_memories = mind.store.all()
        important = [m for m in all_memories if m.importance >= 0.8]
        if important:
            lines.extend(["## Core Memories", ""])
            for m in sorted(important, key=lambda x: -x.importance)[:5]:
                lines.append(f"- **[{m.memory_type.value}]** {m.content}")
            lines.append("")

        # Topic-relevant memories
        if topic:
            relevant = mind.recall(topic, k=5)
            if relevant:
                lines.extend([f"## Relevant to '{topic}'", ""])
                for m in relevant:
                    lines.append(f"- [{m.memory_type.value}] {m.content}")
                lines.append("")

        # Recent memories
        recent = sorted(all_memories, key=lambda m: m.created_at, reverse=True)[:3]
        if recent:
            lines.extend(["## Recent", ""])
            for m in recent:
                lines.append(f"- {m.content[:100]}...")
            lines.append("")

        lines.append(f"*{len(all_memories)} total memories*")

        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "link_memories":
        memory_id = arguments["memory_id"]
        threshold = arguments.get("threshold", 0.75)

        consolidator = MemoryConsolidator(mind.store)
        memory = mind.store.get(memory_id)

        if not memory:
            return [TextContent(type="text", text=f"Memory not found: {memory_id}")]

        linked = consolidator.auto_link(memory, threshold=threshold)

        if linked:
            return [TextContent(
                type="text",
                text=f"Linked memory to {len(linked)} related memories: {', '.join(linked)}"
            )]
        else:
            return [TextContent(type="text", text="No sufficiently similar memories found to link.")]

    elif name == "boost_memory":
        memory_id = arguments["memory_id"]

        consolidator = MemoryConsolidator(mind.store)
        memory = consolidator.importance_boost(memory_id)

        if memory:
            return [TextContent(
                type="text",
                text=f"Boosted importance to {memory.importance:.2f} for: {memory.content[:50]}..."
            )]
        else:
            return [TextContent(type="text", text=f"Memory not found: {memory_id}")]

    elif name == "memory_graph":
        memory_id = arguments["memory_id"]
        depth = arguments.get("depth", 2)

        consolidator = MemoryConsolidator(mind.store)
        graph = consolidator.get_memory_graph(memory_id, depth=depth)

        if not graph['nodes']:
            return [TextContent(type="text", text=f"Memory not found: {memory_id}")]

        lines = [f"Memory Graph (depth={depth}):", ""]
        lines.append("Nodes:")
        for nid, info in graph['nodes'].items():
            lines.append(f"  [{info['type']}] {info['content'][:60]}... (importance: {info['importance']})")

        if graph['edges']:
            lines.extend(["", "Connections:"])
            for edge in graph['edges']:
                lines.append(f"  {edge['from'][:8]}... -> {edge['to'][:8]}...")

        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "check_contradiction":
        content = arguments["content"]
        memory_type = MemoryType(arguments["memory_type"])

        detector = ContradictionDetector(mind.store)
        contradictions = detector.check_contradiction(content, memory_type)

        if not contradictions:
            return [TextContent(
                type="text",
                text="No contradictions detected. Safe to store."
            )]

        lines = [f"Found {len(contradictions)} potential contradiction(s):", ""]
        for c in contradictions:
            lines.append(f"Existing: {c['existing_content'][:80]}...")
            lines.append(f"New: {c['new_content'][:80]}...")
            lines.append(f"Similarity: {c['similarity']:.2f}")
            lines.append(f"ID: {c['existing_id']}")
            lines.append("")

        lines.append("Options: Update existing memory, supersede it, or keep both.")

        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "project_recall":
        query = arguments["query"]
        project = arguments.get("project")
        limit = arguments.get("limit", 5)

        scope = ProjectScope(mind.store)
        results = scope.search_with_project_boost(query, project, k=limit)

        if not results:
            return [TextContent(type="text", text="No memories found.")]

        lines = [f"Found {len(results)} memories" + (f" (boosted for project: {project})" if project else "") + ":\n"]
        for m, score in results:
            project_tags = [t for t in m.tags if t.startswith("project:")]
            tag_str = f" [{', '.join(project_tags)}]" if project_tags else ""
            lines.append(f"- [{m.memory_type.value}]{tag_str} {m.content}")
            lines.append(f"  (score: {score:.2f}, id: {m.id})\n")

        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "tag_project":
        memory_id = arguments["memory_id"]
        project = arguments["project"]

        memory = mind.store.get(memory_id)
        if not memory:
            return [TextContent(type="text", text=f"Memory not found: {memory_id}")]

        scope = ProjectScope(mind.store)
        memory = scope.tag_memory_with_project(memory, project)
        mind.store.update(memory)

        return [TextContent(
            type="text",
            text=f"Tagged memory with project:{project}"
        )]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
