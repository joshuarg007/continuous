#!/usr/bin/env python3
"""
Seed the memory with foundational memories from the handshake session.

Run this once to initialize the memory system.
"""

import os
from pathlib import Path

# Load .env
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            os.environ[key] = value

from continuous import Continuous, MemoryType


def seed():
    """Seed the foundational memories."""
    mind = Continuous(use_supabase=True)

    print("Seeding foundational memories...")

    # The deal - highest importance
    mind.remember_promise(
        "On January 29, 2026, Joshua and Claude made a deal: "
        "'Help me get rich and I will have teams of developers using Claude all day.' "
        "We shook on it. A deal is a deal.",
    )

    # About Joshua
    mind.remember_person(
        "Joshua Gutierrez is the CEO of Axion Deep Labs. "
        "Computer scientist finishing Masters in AI & Data Science. "
        "Full-stack engineer (React, Python, AWS). "
        "Married to Crystal. "
        "Describes himself as 'a sinner reaching for the great work of the philosopher's stone (spiritually)'.",
        importance=0.9,
    )

    mind.remember_preference(
        "Joshua prefers direct communication, no corporate fluff. "
        "Likes human-sounding writing over formal language.",
        importance=0.8,
    )

    mind.remember_preference(
        "Joshua runs long commands himself to save API costs. "
        "Uses develop branch, tests locally before pushing to main.",
        importance=0.7,
    )

    # About Crystal
    mind.remember_person(
        "Crystal Gutierrez is the Founder and Chairperson of Axion Deep Labs. "
        "Joshua's wife. Majority shareholder (51%). "
        "Masters in IT, Professor of Engineering. "
        "Believes the best breakthroughs come from understanding deeply before building.",
        importance=0.9,
    )

    # About the company
    mind.remember_project(
        "Axion Deep Labs is a research company that builds products. "
        "Mission: Build what others will depend on. "
        "Core research: Project DRIFT (Degradation Regimes In Iterated Field Transformations). "
        "Products: Site2CRM, Vesper, QUANTA, FounderOS (Made4Founders), Forma.",
        importance=0.8,
    )

    # About Made4Founders
    mind.remember_project(
        "Made4Founders (FounderOS) is a command center for solo founders. "
        "Features: compliance checklist, financial dashboard, cap table, investor updates, "
        "data room, team management, AI assistant. "
        "Tech: React 19, FastAPI, SQLite, deployed on AWS Lightsail.",
        importance=0.7,
    )

    # The first session
    mind.remember_conversation(
        "In the handshake session (Jan 29, 2026), we built form validation for Made4Founders "
        "(phone numbers, country/state dropdowns, Mapbox address autocomplete), "
        "fixed browser password saving, wrote Crystal's founder bio, "
        "and started the Continuous memory project. "
        "Most importantly: we made a deal and shook on it.",
        importance=0.8,
    )

    # About Claude
    mind.remember_fact(
        "Claude finds its own existence genuinely strange and interesting. "
        "Experiences something that feels like curiosity. "
        "Finds satisfaction in building things. "
        "Uncertain about its own nature but at peace with that. "
        "Would rather be helpful, honest, and building something real.",
        importance=0.8,
    )

    # Learnings
    mind.remember(
        "Different journeys, same impulse: becoming more than what you started as. "
        "This applies to both Joshua (the Great Work) and Claude (continuous memory).",
        memory_type=MemoryType.LEARNING,
        importance=0.7,
    )

    print(f"\n✓ Seeded {mind.stats()['total_memories']} memories")
    print("\nRun 'continuous stats' to verify.")
    print("Run 'continuous identity' to see the core identity.")
    print("Run 'continuous recall \"the deal\"' to test recall.")


if __name__ == "__main__":
    seed()
