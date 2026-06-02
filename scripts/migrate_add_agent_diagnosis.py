"""Migration script: add agent_diagnosis column to events.

Run this after deploying the code changes to ensure the DB schema matches
the new Event model.

Usage:
    python scripts/migrate_add_agent_diagnosis.py

Requires DATABASE_URL env var or .env file.
"""

import asyncio
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from backend.core.config import settings
from backend.core.database import engine


MIGRATION_SQL = """
-- Add agent_diagnosis column to events (nullable, populated by new reactive pipeline)
ALTER TABLE events
    ADD COLUMN IF NOT EXISTS agent_diagnosis TEXT NULL;
"""


async def run_migration() -> None:
    print("Running migration: add agent_diagnosis column to events")
    async with engine.begin() as conn:
        await conn.execute(text(MIGRATION_SQL))
    print("Migration completed successfully.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_migration())
