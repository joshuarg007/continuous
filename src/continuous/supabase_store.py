"""
Supabase-backed vector store for semantic memory.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional
import numpy as np

try:
    from supabase import create_client, Client
except ImportError:
    create_client = None
    Client = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

from continuous.memory import Memory, MemoryType


def load_env():
    """Load .env file if it exists."""
    env_paths = [
        Path.home() / "projects" / "continuous" / ".env",
        Path(__file__).parent.parent.parent / ".env",
        Path.cwd() / ".env",
    ]
    for env_path in env_paths:
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key, value)
            break


class SupabaseStore:
    """Supabase-backed vector store for semantic memory search."""

    def __init__(
        self,
        url: Optional[str] = None,
        key: Optional[str] = None,
        model_name: str = "all-MiniLM-L6-v2",
    ):
        load_env()

        self.url = url or os.environ.get("SUPABASE_URL")
        self.key = key or os.environ.get("SUPABASE_KEY")
        self.model_name = model_name

        if not self.url or not self.key:
            raise ValueError(
                "Supabase credentials required. Set SUPABASE_URL and SUPABASE_KEY "
                "environment variables or pass them directly."
            )

        if create_client is None:
            raise ImportError("supabase not installed. Run: pip install supabase")

        # Initialize Supabase client
        self._client: Client = create_client(self.url, self.key)

        # Initialize embedding model
        self._encoder: Optional[SentenceTransformer] = None

    @property
    def encoder(self) -> SentenceTransformer:
        """Lazy load the encoder."""
        if self._encoder is None:
            if SentenceTransformer is None:
                raise ImportError(
                    "sentence-transformers not installed. "
                    "Run: pip install sentence-transformers"
                )
            self._encoder = SentenceTransformer(self.model_name)
        return self._encoder

    def _embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        embedding = self.encoder.encode([text], normalize_embeddings=True)
        return embedding[0].tolist()

    def add(self, memory: Memory) -> str:
        """Add a memory to the store."""
        # Generate embedding
        embedding = self._embed(memory.content)

        # Insert into Supabase
        data = {
            "id": memory.id,
            "content": memory.content,
            "memory_type": memory.memory_type.value,
            "importance": memory.importance,
            "tags": memory.tags,
            "source": memory.source,
            "related_to": memory.related_to,
            "embedding": embedding,
        }

        self._client.table("memories").insert(data).execute()
        return memory.id

    def search(
        self,
        query: str,
        k: int = 10,
        memory_types: Optional[list[MemoryType]] = None,
        min_importance: float = 0.0,
    ) -> list[tuple[Memory, float]]:
        """Search for similar memories."""
        # Generate query embedding
        query_embedding = self._embed(query)

        # Use the match_memories function
        filter_type = memory_types[0].value if memory_types and len(memory_types) == 1 else None

        response = self._client.rpc(
            "match_memories",
            {
                "query_embedding": query_embedding,
                "match_count": k,
                "filter_type": filter_type,
                "min_importance": min_importance,
            }
        ).execute()

        results = []
        for row in response.data:
            memory = Memory(
                id=row["id"],
                content=row["content"],
                memory_type=MemoryType(row["memory_type"]),
                importance=row["importance"],
                tags=row["tags"] or [],
                source=row["source"],
                created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
            )
            results.append((memory, row["similarity"]))

        # Additional type filtering if multiple types specified
        if memory_types and len(memory_types) > 1:
            results = [(m, s) for m, s in results if m.memory_type in memory_types]

        return results

    def get(self, memory_id: str) -> Optional[Memory]:
        """Get a memory by ID."""
        response = self._client.table("memories").select("*").eq("id", memory_id).execute()

        if not response.data:
            return None

        row = response.data[0]
        return Memory(
            id=row["id"],
            content=row["content"],
            memory_type=MemoryType(row["memory_type"]),
            importance=row["importance"],
            tags=row["tags"] or [],
            source=row["source"],
            related_to=row["related_to"] or [],
            created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")),
        )

    def delete(self, memory_id: str) -> bool:
        """Delete a memory."""
        response = self._client.table("memories").delete().eq("id", memory_id).execute()
        return len(response.data) > 0

    def all(self) -> list[Memory]:
        """Get all memories."""
        response = self._client.table("memories").select("*").order("created_at", desc=True).execute()

        return [
            Memory(
                id=row["id"],
                content=row["content"],
                memory_type=MemoryType(row["memory_type"]),
                importance=row["importance"],
                tags=row["tags"] or [],
                source=row["source"],
                related_to=row["related_to"] or [],
                created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")),
            )
            for row in response.data
        ]

    def count(self) -> int:
        """Get total number of memories."""
        response = self._client.table("memories").select("id", count="exact").execute()
        return response.count or 0

    def clear(self) -> None:
        """Clear all memories. Use with caution."""
        self._client.table("memories").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
