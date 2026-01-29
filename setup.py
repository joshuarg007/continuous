#!/usr/bin/env python3
"""
Setup Supabase database for Continuous.
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

from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: Set SUPABASE_URL and SUPABASE_KEY in .env")
    exit(1)


def setup():
    """Run the schema setup."""
    print(f"Connecting to Supabase: {SUPABASE_URL}")

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Read and execute schema
    schema_path = Path(__file__).parent / "schema.sql"
    schema = schema_path.read_text()

    print("Running schema...")

    # Execute via RPC (need to use postgres directly for DDL)
    # For now, print instructions
    print("\n" + "="*60)
    print("MANUAL STEP REQUIRED")
    print("="*60)
    print("\n1. Go to: https://supabase.com/dashboard/project/ynbeqylytccqjmvzefxw/sql")
    print("2. Paste the contents of schema.sql")
    print("3. Click 'Run'")
    print("\nOr run this in the SQL Editor:\n")
    print(schema)
    print("\n" + "="*60)
    print("\nAfter running the schema, run: python seed.py")


if __name__ == "__main__":
    setup()
