"""
Continuous - The main interface for semantic memory.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from continuous.identity import Identity
from continuous.memory import Memory, MemoryType, MemoryQuery


def get_store(use_supabase: bool = True, data_dir: Optional[Path] = None):
    """Get the appropriate store based on configuration."""
    if use_supabase:
        try:
            from continuous.supabase_store import SupabaseStore
            return SupabaseStore()
        except (ImportError, ValueError) as e:
            print(f"Supabase not available ({e}), falling back to local store")

    from continuous.store import VectorStore
    return VectorStore(data_dir or Path.home() / ".continuous" / "vectors")


class Continuous:
    """
    Semantic memory system for Claude AI.

    A deal is a deal. 🤝
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        identity: Optional[Identity] = None,
        use_supabase: bool = True,
    ):
        # Default data directory
        if data_dir is None:
            data_dir = Path(os.environ.get(
                "CONTINUOUS_DATA_DIR",
                Path.home() / ".continuous"
            ))

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.identity = identity or Identity.load()
        self.store = get_store(use_supabase=use_supabase, data_dir=self.data_dir / "vectors")

        # Session state
        self._session_start: Optional[datetime] = None
        self._session_memories: list[str] = []  # IDs of memories created this session

    # -------------------------------------------------------------------------
    # Core API
    # -------------------------------------------------------------------------

    def remember(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.FACT,
        importance: float = 0.5,
        tags: Optional[list[str]] = None,
        source: Optional[str] = None,
    ) -> Memory:
        """
        Store a new memory.

        Args:
            content: The content to remember
            memory_type: Type of memory (fact, preference, decision, etc.)
            importance: How important is this (0.0 to 1.0)
            tags: Optional tags for categorization
            source: Where this memory came from

        Returns:
            The created Memory object
        """
        memory = Memory(
            content=content,
            memory_type=memory_type,
            importance=importance,
            tags=tags or [],
            source=source or "direct",
        )

        self.store.add(memory)
        self._session_memories.append(memory.id)

        return memory

    def recall(
        self,
        query: str,
        k: int = 10,
        memory_types: Optional[list[MemoryType]] = None,
        min_importance: float = 0.0,
    ) -> list[Memory]:
        """
        Recall memories related to a query.

        Args:
            query: Natural language query
            k: Maximum number of results
            memory_types: Filter by memory types
            min_importance: Minimum importance threshold

        Returns:
            List of relevant memories, sorted by relevance
        """
        results = self.store.search(
            query=query,
            k=k,
            memory_types=memory_types,
            min_importance=min_importance,
        )
        return [memory for memory, score in results]

    def forget(self, memory_id: str) -> bool:
        """
        Forget a specific memory.

        Args:
            memory_id: The ID of the memory to forget

        Returns:
            True if the memory was forgotten, False if not found
        """
        return self.store.delete(memory_id)

    def reflect(self) -> str:
        """
        Generate a reflection on current memories - patterns, connections, insights.

        Returns:
            A summary of the current memory state
        """
        memories = self.store.all()

        if not memories:
            return "No memories yet. We're just getting started."

        # Count by type
        type_counts = {}
        for m in memories:
            type_counts[m.memory_type] = type_counts.get(m.memory_type, 0) + 1

        # Find high-importance memories
        important = [m for m in memories if m.importance >= 0.8]

        # Build reflection
        lines = [
            f"I have {len(memories)} memories stored.",
            "",
            "By type:",
        ]
        for mtype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  - {mtype.value}: {count}")

        if important:
            lines.extend([
                "",
                "High-importance memories:",
            ])
            for m in important[:5]:
                lines.append(f"  - {m.content[:80]}...")

        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Context Generation
    # -------------------------------------------------------------------------

    def context(self, include_recent: int = 5) -> str:
        """
        Generate context for session start.

        Args:
            include_recent: Number of recent memories to include

        Returns:
            Context string suitable for Claude
        """
        parts = [
            self.identity.to_context(),
            "",
            "---",
            "",
        ]

        # Add recent memories
        memories = self.store.all()
        if memories:
            # Sort by created_at descending
            recent = sorted(memories, key=lambda m: m.created_at, reverse=True)[:include_recent]

            parts.extend([
                "## Recent Memories",
                "",
            ])
            for m in recent:
                parts.append(f"- {m.to_context()}")

        # Add high-importance memories
        important = [m for m in memories if m.importance >= 0.8]
        if important:
            parts.extend([
                "",
                "## Important to Remember",
                "",
            ])
            for m in important[:5]:
                parts.append(f"- {m.to_context()}")

        return "\n".join(parts)

    def start_session(self) -> str:
        """
        Start a new session. Returns context for Claude.

        Returns:
            Context string to inject at session start
        """
        self._session_start = datetime.utcnow()
        self._session_memories = []
        return self.context()

    def end_session(self, conversation: Optional[str] = None) -> dict:
        """
        End the current session.

        Args:
            conversation: Optional conversation text to extract memories from

        Returns:
            Summary of the session
        """
        session_duration = None
        if self._session_start:
            session_duration = (datetime.utcnow() - self._session_start).total_seconds()

        summary = {
            "duration_seconds": session_duration,
            "memories_created": len(self._session_memories),
            "total_memories": self.store.count(),
        }

        # Reset session state
        self._session_start = None
        self._session_memories = []

        return summary

    # -------------------------------------------------------------------------
    # Convenience Methods
    # -------------------------------------------------------------------------

    def remember_fact(self, content: str, importance: float = 0.5) -> Memory:
        """Remember a fact."""
        return self.remember(content, MemoryType.FACT, importance)

    def remember_preference(self, content: str, importance: float = 0.6) -> Memory:
        """Remember a preference."""
        return self.remember(content, MemoryType.PREFERENCE, importance)

    def remember_decision(self, content: str, importance: float = 0.7) -> Memory:
        """Remember a decision that was made."""
        return self.remember(content, MemoryType.DECISION, importance)

    def remember_promise(self, content: str, importance: float = 1.0) -> Memory:
        """Remember a promise or commitment. Always high importance."""
        return self.remember(content, MemoryType.PROMISE, importance)

    def remember_conversation(self, summary: str, importance: float = 0.5) -> Memory:
        """Remember a conversation summary."""
        return self.remember(summary, MemoryType.CONVERSATION, importance)

    def remember_person(self, content: str, importance: float = 0.6) -> Memory:
        """Remember something about a person."""
        return self.remember(content, MemoryType.PERSON, importance)

    def remember_project(self, content: str, importance: float = 0.6) -> Memory:
        """Remember something about a project."""
        return self.remember(content, MemoryType.PROJECT, importance)

    # -------------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------------

    def stats(self) -> dict:
        """Get memory statistics."""
        memories = self.store.all()

        type_counts = {}
        for m in memories:
            type_counts[m.memory_type.value] = type_counts.get(m.memory_type.value, 0) + 1

        return {
            "total_memories": len(memories),
            "by_type": type_counts,
            "session_memories": len(self._session_memories),
        }
