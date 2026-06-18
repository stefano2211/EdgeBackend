"""One-shot table creation – run BEFORE multi-worker uvicorn."""

import asyncio
import logging
import sys

from backend.core.database import engine
from backend.persistencia.models import Base  # noqa: F401  (registers all models)
from backend.integrations.models import (  # noqa: F401  (registers integration models)
    IntegrationInstance,
    IntegrationCredential,
)
from backend.integrations.credential_audit import CredentialAuditLog  # noqa: F401
from backend.database_connector.models import DatabaseConnection  # noqa: F401
from backend.database_connector.credential_model import DbConnectionCredential  # noqa: F401


async def _create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


async def _run_migrations() -> None:
    """Apply one-off schema fixes that create_all cannot handle on existing tables."""
    # Migration: drop the unique constraint on dedup_key so that the same
    # alert type can fire multiple times (e.g. same motor overheat on different days).
    # We recreate it as a plain (non-unique) index for query performance.
    migration_sql = """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE tablename = 'events'
              AND indexname = 'idx_event_dedup_key'
              AND indexdef ILIKE '%unique%'
        ) THEN
            DROP INDEX idx_event_dedup_key;
            CREATE INDEX idx_event_dedup_key ON events (dedup_key);
            RAISE NOTICE 'Migration applied: idx_event_dedup_key changed to non-unique';
        END IF;
    END$$;
    """
    async with engine.begin() as conn:
        await conn.exec_driver_sql(migration_sql)
    await engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    logger = logging.getLogger(__name__)
    try:
        asyncio.run(_create_tables())
        logger.info("Database tables ready")
        asyncio.run(_run_migrations())
        logger.info("Database migrations applied")
    except Exception as exc:
        logger.error("Failed to initialize database: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
