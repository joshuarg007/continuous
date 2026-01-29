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

import os


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


class ContradictionDetector:
    """Detects semantic contradictions between memories."""

    # Keywords that indicate preferences/choices (things that can contradict)
    PREFERENCE_SIGNALS = [
        "prefers", "likes", "wants", "uses", "always", "never",
        "should", "must", "don't", "doesn't", "hates", "avoids",
        "favorite", "best", "worst", "instead of", "rather than"
    ]

    def __init__(self, store):
        self.store = store

    def check_contradiction(
        self,
        new_content: str,
        memory_type: MemoryType,
        threshold: float = 0.8
    ) -> list[dict]:
        """
        Check if new content contradicts existing memories.

        Args:
            new_content: The content to check
            memory_type: Type of the new memory
            threshold: Similarity threshold to consider as potential contradiction

        Returns:
            List of potential contradictions with details
        """
        contradictions = []

        # Only check for contradictions in preference/decision/fact types
        if memory_type not in [MemoryType.PREFERENCE, MemoryType.DECISION, MemoryType.FACT]:
            return contradictions

        # Check if content has preference signals
        content_lower = new_content.lower()
        has_preference_signal = any(signal in content_lower for signal in self.PREFERENCE_SIGNALS)

        if not has_preference_signal:
            return contradictions

        # Find semantically similar memories of the same type
        results = self.store.search(new_content, k=5, memory_types=[memory_type])

        for memory, similarity in results:
            if similarity >= threshold:
                # Check for negation patterns
                if self._appears_contradictory(new_content, memory.content):
                    contradictions.append({
                        'existing_id': memory.id,
                        'existing_content': memory.content,
                        'new_content': new_content,
                        'similarity': similarity,
                        'reason': 'High similarity with potential negation/reversal'
                    })

        return contradictions

    def _appears_contradictory(self, new: str, existing: str) -> bool:
        """
        Simple heuristic check for contradictory statements.

        Looks for negation patterns and opposite preference signals.
        """
        new_lower = new.lower()
        existing_lower = existing.lower()

        # Negation patterns
        negations = [
            ("prefers", "doesn't prefer"), ("prefers", "avoids"),
            ("likes", "doesn't like"), ("likes", "hates"),
            ("always", "never"), ("should", "shouldn't"),
            ("uses", "doesn't use"), ("wants", "doesn't want"),
        ]

        for pos, neg in negations:
            if (pos in new_lower and neg in existing_lower) or \
               (neg in new_lower and pos in existing_lower):
                return True

        # Check if both are preferences about same subject but different values
        # e.g., "prefers tabs" vs "prefers spaces"
        if "prefers" in new_lower and "prefers" in existing_lower:
            # Extract what comes after "prefers"
            new_pref = new_lower.split("prefers")[-1].strip()[:30]
            existing_pref = existing_lower.split("prefers")[-1].strip()[:30]
            # If preferences are different but context is similar
            if new_pref != existing_pref:
                return True

        return False

    def resolve_contradiction(
        self,
        existing_id: str,
        new_content: str,
        resolution: str = "supersede"
    ) -> dict:
        """
        Resolve a detected contradiction.

        Args:
            existing_id: ID of the existing memory
            new_content: Content of the new memory
            resolution: How to resolve - "supersede", "keep_both", "update"

        Returns:
            Resolution details
        """
        existing = self.store.get(existing_id)
        if not existing:
            return {'error': 'Existing memory not found'}

        if resolution == "supersede":
            # Mark old as superseded, add reference to new
            existing.tags.append("superseded")
            existing.importance *= 0.5  # Reduce importance
            self.store.update(existing)
            return {
                'action': 'superseded',
                'existing_id': existing_id,
                'message': f'Reduced importance of existing memory, tagged as superseded'
            }

        elif resolution == "update":
            # Update existing memory with new content
            old_content = existing.content
            existing.content = new_content
            existing.updated_at = datetime.utcnow()
            existing.tags.append(f"updated_from:{old_content[:50]}")
            self.store.update(existing)
            return {
                'action': 'updated',
                'existing_id': existing_id,
                'message': 'Updated existing memory with new content'
            }

        else:  # keep_both
            return {
                'action': 'keep_both',
                'message': 'Both memories will be kept'
            }


class ProjectScope:
    """Handles project-aware memory filtering and tagging."""

    # Common project directory patterns
    PROJECT_PATTERNS = [
        r'/projects/([^/]+)',
        r'/([^/]+)$',  # Last directory component
    ]

    def __init__(self, store):
        self.store = store

    def detect_project(self, path: str) -> str | None:
        """
        Detect project name from a path.

        Args:
            path: File system path

        Returns:
            Detected project name or None
        """
        import re

        for pattern in self.PROJECT_PATTERNS:
            match = re.search(pattern, path)
            if match:
                project = match.group(1)
                # Filter out common non-project directories
                if project not in ['home', 'usr', 'var', 'tmp', 'etc']:
                    return project

        return None

    def tag_memory_with_project(self, memory: Memory, project: str) -> Memory:
        """Add project tag to memory."""
        tag = f"project:{project}"
        if tag not in memory.tags:
            memory.tags.append(tag)
        return memory

    def search_with_project_boost(
        self,
        query: str,
        current_project: str | None = None,
        k: int = 10,
        project_boost: float = 0.2
    ) -> list[tuple[Memory, float]]:
        """
        Search memories with boost for current project.

        Args:
            query: Search query
            current_project: Current project name for boosting
            k: Number of results
            project_boost: Score boost for matching project (0-1)

        Returns:
            List of (memory, adjusted_score) tuples
        """
        results = self.store.search(query, k=k * 2)  # Get extra to allow reranking

        if not current_project:
            return results[:k]

        project_tag = f"project:{current_project}"

        # Rerank with project boost
        reranked = []
        for memory, score in results:
            if project_tag in memory.tags:
                adjusted_score = min(1.0, score + project_boost)
            else:
                adjusted_score = score
            reranked.append((memory, adjusted_score))

        # Sort by adjusted score
        reranked.sort(key=lambda x: -x[1])

        return reranked[:k]

    def get_project_memories(self, project: str, limit: int = 20) -> list[Memory]:
        """Get all memories for a specific project."""
        all_memories = self.store.all()
        project_tag = f"project:{project}"

        return [
            m for m in all_memories
            if project_tag in m.tags
        ][:limit]

    def suggest_project_tags(self, memory: Memory) -> list[str]:
        """
        Suggest project tags based on memory content.

        Looks for project names mentioned in the content.
        """
        import re

        suggestions = []
        content_lower = memory.content.lower()

        # Get all existing project tags
        all_memories = self.store.all()
        existing_projects = set()
        for m in all_memories:
            for tag in m.tags:
                if tag.startswith("project:"):
                    existing_projects.add(tag.replace("project:", ""))

        # Check if any existing project is mentioned
        for project in existing_projects:
            if project.lower() in content_lower:
                suggestions.append(f"project:{project}")

        return suggestions


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
