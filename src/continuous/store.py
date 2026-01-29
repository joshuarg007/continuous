"""
Vector store for semantic memory retrieval using FAISS.
"""

import json
import pickle
from pathlib import Path
from typing import Optional
import numpy as np

try:
    import faiss
except ImportError:
    faiss = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

from continuous.memory import Memory, MemoryType


class VectorStore:
    """FAISS-based vector store for semantic memory search."""

    def __init__(
        self,
        data_dir: Path,
        model_name: str = "all-MiniLM-L6-v2",
        dimension: int = 384,
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.dimension = dimension
        self.model_name = model_name

        # Paths
        self.index_path = self.data_dir / "memory.index"
        self.memories_path = self.data_dir / "memories.json"
        self.metadata_path = self.data_dir / "metadata.pkl"

        # Initialize embedding model
        self._encoder: Optional[SentenceTransformer] = None

        # Initialize FAISS index
        self._index: Optional[faiss.Index] = None

        # Memory storage (id -> Memory)
        self._memories: dict[str, Memory] = {}

        # ID mapping (faiss_idx -> memory_id)
        self._id_map: list[str] = []

        # Load existing data
        self._load()

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

    @property
    def index(self) -> faiss.Index:
        """Lazy load or create the FAISS index."""
        if self._index is None:
            if faiss is None:
                raise ImportError("faiss not installed. Run: pip install faiss-cpu")

            if self.index_path.exists():
                self._index = faiss.read_index(str(self.index_path))
            else:
                # Use IndexFlatIP for cosine similarity (after normalization)
                self._index = faiss.IndexFlatIP(self.dimension)
        return self._index

    def _load(self) -> None:
        """Load existing memories and metadata."""
        if self.memories_path.exists():
            with open(self.memories_path, "r") as f:
                data = json.load(f)
                self._memories = {
                    k: Memory(**v) for k, v in data.items()
                }

        if self.metadata_path.exists():
            with open(self.metadata_path, "rb") as f:
                self._id_map = pickle.load(f)

    def _save(self) -> None:
        """Persist memories and index to disk."""
        # Save memories as JSON
        with open(self.memories_path, "w") as f:
            json.dump(
                {k: v.model_dump() for k, v in self._memories.items()},
                f,
                indent=2,
                default=str,
            )

        # Save FAISS index
        if self._index is not None and self._index.ntotal > 0:
            faiss.write_index(self._index, str(self.index_path))

        # Save ID mapping
        with open(self.metadata_path, "wb") as f:
            pickle.dump(self._id_map, f)

    def _embed(self, text: str) -> np.ndarray:
        """Generate embedding for text."""
        embedding = self.encoder.encode([text], normalize_embeddings=True)
        return embedding[0].astype(np.float32)

    def add(self, memory: Memory) -> str:
        """Add a memory to the store."""
        # Generate embedding
        embedding = self._embed(memory.content)
        memory.embedding = embedding.tolist()

        # Add to FAISS
        self.index.add(np.array([embedding]))

        # Store memory and mapping
        self._memories[memory.id] = memory
        self._id_map.append(memory.id)

        # Persist
        self._save()

        return memory.id

    def search(
        self,
        query: str,
        k: int = 10,
        memory_types: Optional[list[MemoryType]] = None,
        min_importance: float = 0.0,
    ) -> list[tuple[Memory, float]]:
        """Search for similar memories."""
        if self.index.ntotal == 0:
            return []

        # Generate query embedding
        query_embedding = self._embed(query)

        # Search FAISS
        k = min(k * 2, self.index.ntotal)  # Get extra results for filtering
        scores, indices = self.index.search(np.array([query_embedding]), k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self._id_map):
                continue

            memory_id = self._id_map[idx]
            memory = self._memories.get(memory_id)

            if memory is None:
                continue

            # Apply filters
            if memory_types and memory.memory_type not in memory_types:
                continue
            if memory.importance < min_importance:
                continue

            results.append((memory, float(score)))

        return results[:k // 2]  # Return original k

    def get(self, memory_id: str) -> Optional[Memory]:
        """Get a memory by ID."""
        return self._memories.get(memory_id)

    def delete(self, memory_id: str) -> bool:
        """Delete a memory. Note: FAISS doesn't support deletion, so we mark as deleted."""
        if memory_id in self._memories:
            del self._memories[memory_id]
            self._save()
            return True
        return False

    def all(self) -> list[Memory]:
        """Get all memories."""
        return list(self._memories.values())

    def count(self) -> int:
        """Get total number of memories."""
        return len(self._memories)

    def clear(self) -> None:
        """Clear all memories. Use with caution."""
        self._memories = {}
        self._id_map = []
        self._index = faiss.IndexFlatIP(self.dimension)
        self._save()
