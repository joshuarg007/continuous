"""
Memory types and structures for Continuous.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid


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


class Memory(BaseModel):
    """A single memory unit."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    memory_type: MemoryType
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Optional metadata
    source: Optional[str] = None  # Where this memory came from
    importance: float = 0.5       # 0.0 to 1.0, how important is this
    tags: list[str] = Field(default_factory=list)

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


class MemoryQuery(BaseModel):
    """A query for retrieving memories."""

    query: str
    memory_types: Optional[list[MemoryType]] = None
    min_importance: float = 0.0
    max_results: int = 10
    tags: Optional[list[str]] = None
    since: Optional[datetime] = None
