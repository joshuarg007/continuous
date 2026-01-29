"""
Memory types and structures for Continuous.
"""

import math
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid


# Decay constants
HALF_LIFE_DAYS = 30  # Memory relevance halves every 30 days
MIN_DECAY_FACTOR = 0.1  # Never decay below 10% relevance


class MemoryType(str, Enum):
    """Types of memories that can be stored."""

    FACT = "fact"              # A discrete piece of information
    PREFERENCE = "preference"  # How someone likes things done
    DECISION = "decision"      # A choice that was made
    CONVERSATION = "conversation"  # Summary of a conversation
    LEARNING = "learning"      # Something discovered or understood
    PERSON = "person"          # Information about a person
    PROJECT = "project"        # Information about a project
    EVENT = "event"            # Something that happened
    PROMISE = "promise"        # A commitment made


class SourceType(str, Enum):
    """How the memory was acquired."""

    USER_STATED = "user_stated"      # User explicitly said this
    INFERRED = "inferred"            # Claude concluded this from context
    FILE = "file"                    # Extracted from a document
    CORRECTED = "corrected"          # User corrected a previous memory
    AUTO_EXTRACTED = "auto_extracted"  # Extracted by post-conversation hook


class Memory(BaseModel):
    """A single memory unit."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    memory_type: MemoryType
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Optional metadata
    source: Optional[str] = None  # Free-form source description
    importance: float = 0.5       # 0.0 to 1.0, how important is this
    tags: list[str] = Field(default_factory=list)

    # Source tracking (v2)
    source_type: SourceType = SourceType.INFERRED
    confidence: float = 1.0       # 0.0 to 1.0, how certain
    project: Optional[str] = None  # Project this memory belongs to

    # Token management (v2)
    token_count: Optional[int] = None

    # Model tracking for migration (v2)
    embedding_model: str = "all-MiniLM-L6-v2"

    # Verification (v2)
    last_verified_at: Optional[datetime] = None
    verification_count: int = 0

    # Version history (v2)
    previous_version_id: Optional[str] = None
    superseded_by_id: Optional[str] = None

    # Relationships
    related_to: list[str] = Field(default_factory=list)  # IDs of related memories

    # For vector storage
    embedding: Optional[list[float]] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    def __str__(self) -> str:
        return f"[{self.memory_type.value}] {self.content[:100]}..."

    def to_context(self) -> str:
        """Format memory for inclusion in context."""
        prefix = {
            MemoryType.FACT: "Fact:",
            MemoryType.PREFERENCE: "Preference:",
            MemoryType.DECISION: "Decision:",
            MemoryType.CONVERSATION: "From conversation:",
            MemoryType.LEARNING: "Learned:",
            MemoryType.PERSON: "About person:",
            MemoryType.PROJECT: "About project:",
            MemoryType.EVENT: "Event:",
            MemoryType.PROMISE: "Promise:",
        }
        return f"{prefix.get(self.memory_type, '')} {self.content}"

    def temporal_decay(self, as_of: datetime = None) -> float:
        """
        Calculate temporal decay factor based on age.

        Memories decay over time unless they're high importance.
        Promises and high-importance memories (>=0.9) don't decay.

        Returns:
            Decay factor between MIN_DECAY_FACTOR and 1.0
        """
        # Promises and critical memories don't decay
        if self.memory_type == MemoryType.PROMISE or self.importance >= 0.9:
            return 1.0

        as_of = as_of or datetime.utcnow()
        age_days = (as_of - self.created_at).days

        if age_days <= 0:
            return 1.0

        # Exponential decay with half-life
        decay = math.pow(0.5, age_days / HALF_LIFE_DAYS)

        # Never decay below minimum
        return max(decay, MIN_DECAY_FACTOR)

    def effective_score(self, similarity: float, as_of: datetime = None) -> float:
        """
        Calculate effective relevance score combining similarity, importance, recency, and confidence.

        Args:
            similarity: Vector similarity score (0-1)
            as_of: Time to calculate decay from

        Returns:
            Combined score weighted by importance, recency, and confidence
        """
        decay = self.temporal_decay(as_of)

        # Weight: 40% similarity, 25% importance, 20% recency, 15% confidence
        base_score = (0.4 * similarity) + (0.25 * self.importance) + (0.2 * decay) + (0.15 * self.confidence)

        # Boost for user_stated sources (most reliable)
        if self.source_type == SourceType.USER_STATED:
            base_score *= 1.1

        return min(1.0, base_score)

    def estimate_tokens(self) -> int:
        """
        Estimate token count for context budget.

        Rough estimate: ~4 chars per token for English text.
        """
        if self.token_count:
            return self.token_count

        # Rough estimation
        base_tokens = len(self.content) // 4

        # Add overhead for metadata in context
        overhead = 10  # Type label, formatting

        return base_tokens + overhead

    def verify(self) -> None:
        """Mark memory as verified (user confirmed it's still accurate)."""
        self.last_verified_at = datetime.utcnow()
        self.verification_count += 1
        # Boost confidence slightly when verified
        self.confidence = min(1.0, self.confidence + 0.1)

    def needs_verification(self, days_threshold: int = 30) -> bool:
        """Check if memory should be re-verified."""
        if self.last_verified_at is None:
            # Never verified, check age
            age_days = (datetime.utcnow() - self.created_at).days
            return age_days > days_threshold

        days_since_verify = (datetime.utcnow() - self.last_verified_at).days
        return days_since_verify > days_threshold


class MemoryQuery(BaseModel):
    """A query for retrieving memories."""

    query: str
    memory_types: Optional[list[MemoryType]] = None
    min_importance: float = 0.0
    max_results: int = 10
    tags: Optional[list[str]] = None
    since: Optional[datetime] = None
