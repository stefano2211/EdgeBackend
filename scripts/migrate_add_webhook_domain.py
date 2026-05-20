"""Migration script: add domain column to webhook_sources.

Run this after deploying the code changes to ensure the DB schema matches
the new WebhookSource model.

Usage:
    python scripts/migrate_add_webhook_domain.py

Requires DATABASE_URL env var or .env file.
"""

import asyncio
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.core.config import settings
from src.core.database import engine


MIGRATION_SQL = """
-- Add domain column to webhook_sources (nullable, populated automatically on first event)
ALTER TABLE webhook_sources
    ADD COLUMN IF NOT EXISTS domain VARCHAR(50) NULL;

-- Optional: index for fast filtering by domain
CREATE INDEX IF NOT EXISTS idx_webhook_domain
    ON webhook_sources(domain);
"""


async def run_migration() -> None:
    print("Running migration: add domain column to webhook_sources")
    async with engine.begin() as conn:
        await conn.execute(text(MIGRATION_SQL))
    print("Migration completed successfully.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_migration())
