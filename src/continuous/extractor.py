"""
Auto-extraction of memories from conversations.

This module extracts key information from conversation transcripts
without requiring Claude to explicitly call remember().
"""

import re
from typing import Optional
from datetime import datetime

from continuous.memory import Memory, MemoryType, SourceType


# Patterns that indicate extractable content
DECISION_PATTERNS = [
    r"(?:we |I )?(?:decided|chose|went with|picked|selected|will use|going with)\s+(.+?)(?:\.|$)",
    r"(?:the |our )?decision(?:is| was)?\s*(?:to |:)\s*(.+?)(?:\.|$)",
    r"let's (?:go with|use|do)\s+(.+?)(?:\.|$)",
]

PREFERENCE_PATTERNS = [
    r"(?:I |user |joshua |crystal )?(?:prefer|like|want|always|never)\s+(.+?)(?:\.|$)",
    r"(?:my |his |her |their )?preference is\s+(.+?)(?:\.|$)",
]

FACT_PATTERNS = [
    r"(?:turns out|actually|found out|discovered|learned)\s+(?:that\s+)?(.+?)(?:\.|$)",
    r"(?:the |this )?(?:code|file|function|api|system)\s+(?:is|does|has)\s+(.+?)(?:\.|$)",
]

PROMISE_PATTERNS = [
    r"(?:I |we )(?:promise|commit|guarantee|will definitely)\s+(.+?)(?:\.|$)",
    r"(?:deal|agreement|commitment)(?::|\s+is)\s+(.+?)(?:\.|$)",
]


class ConversationExtractor:
    """Extracts memories from conversation transcripts."""

    def __init__(self, min_confidence: float = 0.6):
        """
        Args:
            min_confidence: Minimum confidence to include extracted memories
        """
        self.min_confidence = min_confidence

    def extract(self, conversation: str, project: Optional[str] = None) -> list[Memory]:
        """
        Extract memories from a conversation transcript.

        Args:
            conversation: The full conversation text
            project: Optional project to tag memories with

        Returns:
            List of extracted Memory objects
        """
        memories = []

        # Extract different types
        memories.extend(self._extract_decisions(conversation, project))
        memories.extend(self._extract_preferences(conversation, project))
        memories.extend(self._extract_facts(conversation, project))
        memories.extend(self._extract_promises(conversation, project))

        # Deduplicate by content similarity
        unique = self._deduplicate(memories)

        return unique

    def _extract_decisions(self, text: str, project: Optional[str]) -> list[Memory]:
        """Extract decision memories."""
        memories = []

        for pattern in DECISION_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                content = self._clean_content(match)
                if len(content) > 10:  # Skip very short matches
                    memories.append(Memory(
                        content=f"Decision: {content}",
                        memory_type=MemoryType.DECISION,
                        importance=0.7,
                        source_type=SourceType.AUTO_EXTRACTED,
                        confidence=0.7,
                        project=project,
                        source="conversation_extraction",
                    ))

        return memories

    def _extract_preferences(self, text: str, project: Optional[str]) -> list[Memory]:
        """Extract preference memories."""
        memories = []

        for pattern in PREFERENCE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                content = self._clean_content(match)
                if len(content) > 10:
                    memories.append(Memory(
                        content=f"Preference: {content}",
                        memory_type=MemoryType.PREFERENCE,
                        importance=0.6,
                        source_type=SourceType.AUTO_EXTRACTED,
                        confidence=0.6,
                        project=project,
                        source="conversation_extraction",
                    ))

        return memories

    def _extract_facts(self, text: str, project: Optional[str]) -> list[Memory]:
        """Extract fact memories."""
        memories = []

        for pattern in FACT_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                content = self._clean_content(match)
                if len(content) > 15:  # Facts should be more substantial
                    memories.append(Memory(
                        content=content,
                        memory_type=MemoryType.FACT,
                        importance=0.5,
                        source_type=SourceType.AUTO_EXTRACTED,
                        confidence=0.5,
                        project=project,
                        source="conversation_extraction",
                    ))

        return memories

    def _extract_promises(self, text: str, project: Optional[str]) -> list[Memory]:
        """Extract promise memories."""
        memories = []

        for pattern in PROMISE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                content = self._clean_content(match)
                if len(content) > 10:
                    memories.append(Memory(
                        content=f"Promise: {content}",
                        memory_type=MemoryType.PROMISE,
                        importance=0.9,  # Promises are important
                        source_type=SourceType.AUTO_EXTRACTED,
                        confidence=0.8,  # But auto-extracted, so not 1.0
                        project=project,
                        source="conversation_extraction",
                    ))

        return memories

    def _clean_content(self, content: str) -> str:
        """Clean extracted content."""
        # Remove extra whitespace
        content = " ".join(content.split())
        # Remove leading/trailing punctuation
        content = content.strip(".,;:\"'")
        # Capitalize first letter
        if content:
            content = content[0].upper() + content[1:]
        return content

    def _deduplicate(self, memories: list[Memory]) -> list[Memory]:
        """Remove near-duplicate memories."""
        unique = []
        seen_content = set()

        for memory in memories:
            # Normalize for comparison
            normalized = memory.content.lower().strip()

            # Check for exact or near duplicates
            is_duplicate = False
            for seen in seen_content:
                if self._is_similar(normalized, seen):
                    is_duplicate = True
                    break

            if not is_duplicate:
                seen_content.add(normalized)
                unique.append(memory)

        return unique

    def _is_similar(self, a: str, b: str, threshold: float = 0.8) -> bool:
        """Check if two strings are similar using simple Jaccard similarity."""
        words_a = set(a.split())
        words_b = set(b.split())

        if not words_a or not words_b:
            return False

        intersection = len(words_a & words_b)
        union = len(words_a | words_b)

        return (intersection / union) >= threshold


def extract_from_transcript(
    transcript_path: str,
    project: Optional[str] = None,
) -> list[Memory]:
    """
    Convenience function to extract from a transcript file.

    Args:
        transcript_path: Path to conversation transcript
        project: Optional project tag

    Returns:
        List of extracted memories
    """
    with open(transcript_path, 'r') as f:
        content = f.read()

    extractor = ConversationExtractor()
    return extractor.extract(content, project)
