#!/usr/bin/env python3
"""
Claude Code hooks for automatic memory integration.

These hooks run automatically:
- On session start: Inject relevant context
- On session end: Extract and store conversation memories
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path


def get_mind():
    """Get Continuous instance with proper environment."""
    # Ensure environment is set
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key, value)

    from continuous.core import Continuous
    return Continuous(use_supabase=True)


def session_start_hook():
    """
    Hook: Inject context at session start.

    Outputs markdown context that Claude Code can use.
    """
    try:
        mind = get_mind()

        # Build context
        lines = [
            "# Continuous Memory Context",
            "",
            mind.identity.to_context(),
            "",
            "---",
            "",
        ]

        # High-importance memories (promises, key facts)
        important = [m for m in mind.store.all() if m.importance >= 0.8]
        if important:
            lines.extend([
                "## Core Memories",
                "",
            ])
            for m in sorted(important, key=lambda x: -x.importance)[:5]:
                lines.append(f"- **[{m.memory_type.value}]** {m.content}")
            lines.append("")

        # Recent memories
        all_memories = mind.store.all()
        if all_memories:
            recent = sorted(all_memories, key=lambda m: m.created_at, reverse=True)[:3]
            lines.extend([
                "## Recent",
                "",
            ])
            for m in recent:
                lines.append(f"- {m.content[:100]}{'...' if len(m.content) > 100 else ''}")
            lines.append("")

        # Stats
        stats = mind.stats()
        lines.extend([
            f"*{stats['total_memories']} memories stored*",
        ])

        print("\n".join(lines))

    except Exception as e:
        print(f"[Continuous] Could not load context: {e}", file=sys.stderr)


def session_end_hook(conversation_summary: str = None):
    """
    Hook: Store conversation summary at session end.

    Args:
        conversation_summary: Optional summary to store
    """
    try:
        if not conversation_summary:
            return

        mind = get_mind()
        mind.remember_conversation(
            f"Session ended {datetime.utcnow().isoformat()}: {conversation_summary}",
            importance=0.5,
        )
        print(f"[Continuous] Session memory stored", file=sys.stderr)

    except Exception as e:
        print(f"[Continuous] Could not store session: {e}", file=sys.stderr)


if __name__ == "__main__":
    # CLI interface for hooks
    if len(sys.argv) > 1:
        if sys.argv[1] == "start":
            session_start_hook()
        elif sys.argv[1] == "end":
            summary = sys.argv[2] if len(sys.argv) > 2 else None
            session_end_hook(summary)
    else:
        # Default: show context
        session_start_hook()
