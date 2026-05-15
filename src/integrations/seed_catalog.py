"""Seed script — populates integration_catalog with pre-configured entries.

Run manually:
    uv run python -m src.integrations.seed_catalog
"""

from __future__ import annotations

import asyncio
import logging

from src.core.database import AsyncSessionLocal
from src.integrations.catalog_seed import seed_integration_catalog

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def main() -> None:
    async with AsyncSessionLocal() as session:
        created, skipped = await seed_integration_catalog(session)
        logger.info("Manual seed complete: %d created, %d skipped", created, skipped)


if __name__ == "__main__":
    asyncio.run(main())
