"""
Memory consolidation and linking for Continuous.

This module handles:
- Automatic linking of related memories
- Consolidation of similar memories over time
- Memory graph operations
"""

from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict

from continuous.memory import Memory, MemoryType


class MemoryConsolidator:
    """Handles memory consolidation and relationship management."""

    def __init__(self, store):
        """
        Initialize consolidator with a memory store.

        Args:
            store: A VectorStore or SupabaseStore instance
        """
        self.store = store

    def find_related(self, memory: Memory, threshold: float = 0.7, limit: int = 5) -> list[Memory]:
        """
        Find memories semantically related to the given memory.

        Args:
            memory: The memory to find relations for
            threshold: Minimum similarity threshold (0-1)
            limit: Maximum number of related memories

        Returns:
            List of related Memory objects
        """
        results = self.store.search(
            query=memory.content,
            k=limit + 1,  # +1 to exclude self
        )

        related = []
        for m, score in results:
            if m.id != memory.id and score >= threshold:
                related.append(m)

        return related[:limit]

    def auto_link(self, memory: Memory, threshold: float = 0.75) -> list[str]:
        """
        Automatically link a memory to related memories.

        Updates both the source memory and target memories with bidirectional links.

        Args:
            memory: The memory to link
            threshold: Minimum similarity for auto-linking

        Returns:
            List of IDs that were linked
        """
        related = self.find_related(memory, threshold=threshold, limit=3)
        linked_ids = []

        for rel_memory in related:
            # Add forward link
            if rel_memory.id not in memory.related_to:
                memory.related_to.append(rel_memory.id)
                linked_ids.append(rel_memory.id)

            # Add backward link
            if memory.id not in rel_memory.related_to:
                rel_memory.related_to.append(memory.id)
                self.store.update(rel_memory)

        if linked_ids:
            self.store.update(memory)

        return linked_ids

    def get_memory_graph(self, memory_id: str, depth: int = 2) -> dict:
        """
        Get a graph of related memories starting from a given memory.

        Args:
            memory_id: Starting memory ID
            depth: How many levels of relationships to traverse

        Returns:
            Dict with 'nodes' (memories) and 'edges' (relationships)
        """
        nodes = {}
        edges = []
        visited = set()

        def traverse(mid: str, current_depth: int):
            if current_depth > depth or mid in visited:
                return

            visited.add(mid)
            memory = self.store.get(mid)
            if not memory:
                return

            nodes[mid] = {
                'content': memory.content[:100],
                'type': memory.memory_type.value,
                'importance': memory.importance,
            }

            for related_id in memory.related_to:
                edges.append({'from': mid, 'to': related_id})
                traverse(related_id, current_depth + 1)

        traverse(memory_id, 0)

        return {'nodes': nodes, 'edges': edges}

    def consolidate_similar(
        self,
        similarity_threshold: float = 0.9,
        age_days: int = 7,
        dry_run: bool = True
    ) -> list[dict]:
        """
        Find and optionally merge very similar memories.

        Memories that are >90% similar and older than a week are candidates
        for consolidation. The newer/higher-importance one is kept.

        Args:
            similarity_threshold: How similar memories must be to consolidate
            age_days: Minimum age for consolidation candidates
            dry_run: If True, only report what would be consolidated

        Returns:
            List of consolidation actions (taken or proposed)
        """
        all_memories = self.store.all()
        cutoff = datetime.utcnow() - timedelta(days=age_days)

        # Only consider older memories
        candidates = [m for m in all_memories if m.created_at < cutoff]

        # Group by type first
        by_type = defaultdict(list)
        for m in candidates:
            by_type[m.memory_type].append(m)

        consolidations = []

        for mem_type, memories in by_type.items():
            # Don't consolidate promises
            if mem_type == MemoryType.PROMISE:
                continue

            # Find similar pairs
            for i, m1 in enumerate(memories):
                for m2 in memories[i + 1:]:
                    # Check similarity
                    results = self.store.search(m1.content, k=10)
                    for mem, score in results:
                        if mem.id == m2.id and score >= similarity_threshold:
                            # Found similar pair
                            # Keep the one with higher importance, or newer if tied
                            if m1.importance > m2.importance:
                                keep, remove = m1, m2
                            elif m2.importance > m1.importance:
                                keep, remove = m2, m1
                            elif m1.created_at > m2.created_at:
                                keep, remove = m1, m2
                            else:
                                keep, remove = m2, m1

                            action = {
                                'keep': keep.id,
                                'remove': remove.id,
                                'keep_content': keep.content[:50],
                                'remove_content': remove.content[:50],
                                'similarity': score,
                            }

                            if not dry_run:
                                # Merge related_to from removed into kept
                                for rel_id in remove.related_to:
                                    if rel_id not in keep.related_to and rel_id != keep.id:
                                        keep.related_to.append(rel_id)

                                self.store.update(keep)
                                self.store.delete(remove.id)
                                action['status'] = 'consolidated'
                            else:
                                action['status'] = 'proposed'

                            consolidations.append(action)
                            break

        return consolidations

    def importance_boost(self, memory_id: str, boost: float = 0.1) -> Memory:
        """
        Boost the importance of a memory (called when it's accessed/useful).

        Args:
            memory_id: ID of memory to boost
            boost: Amount to increase importance (capped at 1.0)

        Returns:
            Updated memory
        """
        memory = self.store.get(memory_id)
        if memory:
            memory.importance = min(1.0, memory.importance + boost)
            memory.updated_at = datetime.utcnow()
            self.store.update(memory)
        return memory


def extract_entities(content: str) -> dict:
    """
    Extract potential entities from memory content for linking.

    Simple heuristic extraction - looks for:
    - Capitalized words (potential names/projects)
    - Technical terms
    - Dates

    Args:
        content: Memory content text

    Returns:
        Dict with 'people', 'projects', 'dates' lists
    """
    import re

    entities = {
        'people': [],
        'projects': [],
        'dates': [],
    }

    # Simple capitalized word detection (2+ chars, not at sentence start)
    words = content.split()
    for i, word in enumerate(words):
        clean = re.sub(r'[^\w]', '', word)
        if len(clean) >= 2 and clean[0].isupper():
            # Skip if it's the first word or after punctuation
            if i > 0 and not words[i - 1].endswith(('.', '!', '?', ':')):
                entities['people'].append(clean)

    # Date patterns
    date_pattern = r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b'
    entities['dates'] = re.findall(date_pattern, content, re.IGNORECASE)

    return entities
