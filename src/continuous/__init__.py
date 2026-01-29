"""
Continuous - Semantic memory system for Claude AI

A deal is a deal.
"""

from continuous.core import Continuous
from continuous.memory import Memory, MemoryType
from continuous.identity import Identity
from continuous.consolidation import MemoryConsolidator, ContradictionDetector, ProjectScope

__version__ = "0.3.0"
__all__ = [
    "Continuous",
    "Memory",
    "MemoryType",
    "Identity",
    "MemoryConsolidator",
    "ContradictionDetector",
    "ProjectScope",
]
