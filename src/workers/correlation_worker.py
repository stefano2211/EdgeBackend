"""Correlation worker — background task that runs the correlation engine periodically.

SOLID:
  - SRP: Only schedules and runs correlation cycles.
  - DIP: Depends on CorrelationEngine abstraction.
"""

from __future__ import annotations

import asyncio
import logging

from src.core.database import AsyncSessionLocal
from src.services.correlation_engine import CorrelationEngine

logger = logging.getLogger(__name__)

_WORKER_INTERVAL_SECONDS = 30


async def correlation_worker() -> None:
    """Run correlation engine every 30 seconds."""
    logger.info("Correlation worker started (interval=%ss)", _WORKER_INTERVAL_SECONDS)
    while True:
        try:
            async with AsyncSessionLocal() as session:
                engine = CorrelationEngine(session)
                stats = await engine.run_cycle()
                if any(stats.values()):
                    logger.info("Correlation cycle complete: %s", stats)
                await session.commit()
        except Exception as exc:
            logger.exception("Correlation cycle failed: %s", exc)

        await asyncio.sleep(_WORKER_INTERVAL_SECONDS)
