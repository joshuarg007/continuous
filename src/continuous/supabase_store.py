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

from continuous.memory import Memory, MemoryType, SourceType


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

        # Estimate token count
        if memory.token_count is None:
            memory.token_count = memory.estimate_tokens()

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
            # v2 fields
            "source_type": memory.source_type.value,
            "confidence": memory.confidence,
            "project": memory.project,
            "token_count": memory.token_count,
            "embedding_model": memory.embedding_model,
        }

        self._client.table("memories").insert(data).execute()
        return memory.id

    def search(
        self,
        query: str,
        k: int = 10,
        memory_types: Optional[list[MemoryType]] = None,
        min_importance: float = 0.0,
        project: Optional[str] = None,
        min_confidence: float = 0.0,
    ) -> list[tuple[Memory, float]]:
        """Search for similar memories."""
        # Generate query embedding
        query_embedding = self._embed(query)

        # Use the match_memories function
        filter_type = memory_types[0].value if memory_types and len(memory_types) == 1 else None

        rpc_params = {
            "query_embedding": query_embedding,
            "match_count": k,
            "filter_type": filter_type,
            "min_importance": min_importance,
        }

        # Add v2 params if the function supports them (graceful fallback)
        if project:
            rpc_params["filter_project"] = project
        if min_confidence > 0:
            rpc_params["min_confidence"] = min_confidence

        try:
            response = self._client.rpc("match_memories", rpc_params).execute()
        except Exception:
            # Fallback for older schema without v2 params
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
            # Build memory with available fields
            memory = Memory(
                id=row["id"],
                content=row["content"],
                memory_type=MemoryType(row["memory_type"]),
                importance=row["importance"],
                tags=row["tags"] or [],
                source=row["source"],
                created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
                # v2 fields (may not be in response from older schema)
                source_type=SourceType(row.get("source_type", "inferred")),
                confidence=row.get("confidence", 1.0),
                project=row.get("project"),
            )
            results.append((memory, row["similarity"]))

        # Additional type filtering if multiple types specified
        if memory_types and len(memory_types) > 1:
            results = [(m, s) for m, s in results if m.memory_type in memory_types]

        return results

    def _row_to_memory(self, row: dict) -> Memory:
        """Convert a database row to a Memory object."""
        # Handle optional v2 fields gracefully (they may not exist in older records)
        source_type = SourceType(row.get("source_type", "inferred"))
        confidence = row.get("confidence", 1.0)
        project = row.get("project")
        token_count = row.get("token_count")
        embedding_model = row.get("embedding_model", "all-MiniLM-L6-v2")
        last_verified_at = None
        if row.get("last_verified_at"):
            last_verified_at = datetime.fromisoformat(row["last_verified_at"].replace("Z", "+00:00"))
        verification_count = row.get("verification_count", 0)
        previous_version_id = row.get("previous_version_id")
        superseded_by_id = row.get("superseded_by_id")

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
            # v2 fields
            source_type=source_type,
            confidence=confidence,
            project=project,
            token_count=token_count,
            embedding_model=embedding_model,
            last_verified_at=last_verified_at,
            verification_count=verification_count,
            previous_version_id=previous_version_id,
            superseded_by_id=superseded_by_id,
        )

    def get(self, memory_id: str) -> Optional[Memory]:
        """Get a memory by ID."""
        response = self._client.table("memories").select("*").eq("id", memory_id).execute()

        if not response.data:
            return None

        return self._row_to_memory(response.data[0])

    def delete(self, memory_id: str) -> bool:
        """Delete a memory."""
        response = self._client.table("memories").delete().eq("id", memory_id).execute()
        return len(response.data) > 0

    def update(self, memory: Memory) -> bool:
        """Update an existing memory."""
        data = {
            "content": memory.content,
            "memory_type": memory.memory_type.value,
            "importance": memory.importance,
            "tags": memory.tags,
            "source": memory.source,
            "related_to": memory.related_to,
            "updated_at": datetime.utcnow().isoformat(),
            # v2 fields
            "source_type": memory.source_type.value,
            "confidence": memory.confidence,
            "project": memory.project,
            "token_count": memory.token_count or memory.estimate_tokens(),
            "last_verified_at": memory.last_verified_at.isoformat() if memory.last_verified_at else None,
            "verification_count": memory.verification_count,
            "previous_version_id": memory.previous_version_id,
            "superseded_by_id": memory.superseded_by_id,
        }

        # Re-embed if content changed (check by fetching current)
        current = self.get(memory.id)
        if current and current.content != memory.content:
            data["embedding"] = self._embed(memory.content)
            data["embedding_model"] = self.model_name

        response = self._client.table("memories").update(data).eq("id", memory.id).execute()
        return len(response.data) > 0

    def all(self, project: Optional[str] = None) -> list[Memory]:
        """Get all memories, optionally filtered by project."""
        query = self._client.table("memories").select("*").order("created_at", desc=True)

        if project:
            query = query.eq("project", project)

        response = query.execute()

        return [self._row_to_memory(row) for row in response.data]

    def needs_verification(self, days_threshold: int = 30, limit: int = 10) -> list[Memory]:
        """Get memories that need re-verification."""
        all_memories = self.all()
        return [
            m for m in all_memories
            if m.needs_verification(days_threshold)
        ][:limit]

    def by_project(self, project: str) -> list[Memory]:
        """Get all memories for a specific project."""
        return self.all(project=project)

    def re_embed_all(self, new_model_name: Optional[str] = None) -> int:
        """Re-embed all memories with current or new model. Returns count."""
        if new_model_name:
            self.model_name = new_model_name
            self._encoder = None  # Force reload

        memories = self.all()
        count = 0

        for memory in memories:
            embedding = self._embed(memory.content)
            self._client.table("memories").update({
                "embedding": embedding,
                "embedding_model": self.model_name,
            }).eq("id", memory.id).execute()
            count += 1

        return count

    def count(self) -> int:
        """Get total number of memories."""
        response = self._client.table("memories").select("id", count="exact").execute()
        return response.count or 0

    def clear(self) -> None:
        """Clear all memories. Use with caution."""
        self._client.table("memories").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
