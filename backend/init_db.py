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


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    logger = logging.getLogger(__name__)
    try:
        asyncio.run(_create_tables())
        logger.info("Database tables ready")
    except Exception as exc:
        logger.error("Failed to create tables: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
