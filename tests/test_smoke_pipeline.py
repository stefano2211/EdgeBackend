"""Integration smoke test for the sector-agnostic event pipeline.

Tests:
  1. Domain detection (rule-based + LLM fallback)
  2. Event creation with normalization
  3. Event repository filtering
  4. Correlation engine cycle
  5. Metric recording
"""

import asyncio
import os
import sys

# Ensure project root is on path for backend.* imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Override DB to use 127.0.0.1 for local testing
os.environ["DATABASE_URL"] = "postgresql+asyncpg://edge:edge@127.0.0.1:5432/edgebackend"

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import AsyncSessionLocal
from backend.persistencia.models import Event, DomainConfig, EventCorrelationGroup, EventMetric, UserFeedback
from backend.persistencia.repositories.event_repository import EventRepository
from backend.persistencia.repositories.domain_config_repository import DomainConfigRepository
from backend.services.domain_detector import DomainDetector
from backend.services.correlation_engine import CorrelationEngine
from backend.services.event_metric_service import EventMetricService
from backend.api.v1.schemas.event import EventIngestPayload, severity_text_to_number


async def _ensure_test_user(session: AsyncSession) -> int:
    """Create a test user if not exists."""
    from sqlalchemy import text
    res = await session.execute(text("SELECT id FROM users WHERE username = 'smoke_test_user'"))
    row = res.scalar_one_or_none()
    if row:
        return row
    await session.execute(text(
        "INSERT INTO users (username, email, hashed_password, role, is_active) "
        "VALUES ('smoke_test_user', 'smoke@test.com', 'fakehash', 'user', true) RETURNING id"
    ))
    await session.commit()
    res = await session.execute(text("SELECT id FROM users WHERE username = 'smoke_test_user'"))
    return res.scalar_one()


async def _reset_test_data(session: AsyncSession, user_id: int) -> None:
    """Clean up test artifacts."""
    from sqlalchemy import text
    await session.execute(text("DELETE FROM user_feedback WHERE event_id IN (SELECT id FROM events WHERE title LIKE 'SMOKE TEST%')"))
    await session.execute(text("DELETE FROM events WHERE title LIKE 'SMOKE TEST%'"))
    await session.execute(text("DELETE FROM domain_configs WHERE user_id = :uid"), {"uid": user_id})
    await session.execute(text("DELETE FROM event_metrics WHERE domain = 'smoke_test_domain'"))
    await session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
    await session.commit()


async def main() -> int:
    async with AsyncSessionLocal() as session:
        user_id = await _ensure_test_user(session)
        # Clean artifacts but keep the test user alive
        from sqlalchemy import text
        await session.execute(text("DELETE FROM user_feedback WHERE event_id IN (SELECT id FROM events WHERE title LIKE 'SMOKE TEST%')"))
        await session.execute(text("DELETE FROM events WHERE title LIKE 'SMOKE TEST%'"))
        await session.execute(text("DELETE FROM domain_configs WHERE user_id = :uid"), {"uid": user_id})
        await session.execute(text("DELETE FROM event_metrics WHERE domain = 'smoke_test_domain'"))
        await session.commit()

        print("\n=== Aura AI Sector-Agnostic Pipeline Smoke Test ===\n")

        # ── 1. Domain Config & Detection ──
        print("[1] Domain detection...")
        domain_repo = DomainConfigRepository(session)
        detector = DomainDetector(domain_repo)

        # Test LLM fallback (no user domains yet)
        result = await detector.detect(
            payload={"patient_id": "P123", "ward": "ICU", "heart_rate": 140},
            user_id=None,
            source="hospital-monitor-01",
        )
        assert "domain" in result, "Domain detection must return 'domain'"
        print(f"   LLM inference -> domain={result['domain']} (confidence={result['confidence']})")

        # Create a user domain config
        domain = DomainConfig(
            user_id=user_id,
            name="smoke_healthcare",
            display_name="Smoke Healthcare",
            detection_rules={"keywords": ["patient", "ward"], "source_patterns": ["hospital-*"]},
        )
        session.add(domain)
        await session.commit()

        # Test rule-based detection
        result2 = await detector.detect(
            payload={"patient_id": "P456"},
            user_id=user_id,
            source="hospital-monitor-02",
        )
        assert result2["source"] == "rule", "Should match rule-based detection"
        print(f"   Rule match -> domain={result2['domain']} (source={result2['source']})")

        # ── 2. Event Creation ──
        print("\n[2] Event creation with normalization...")
        event_repo = EventRepository(session)

        event = Event(
            event_id="smoke-ev-001",
            event_type="alert",
            source="hospital-monitor-01",
            timestamp=__import__("datetime").datetime.utcnow(),
            severity_number=severity_text_to_number("critical"),
            severity_text="critical",
            title="SMOKE TEST: High heart rate",
            description="Patient heart rate elevated",
            body={"patient_id": "P123", "heart_rate": 140},
            domain="healthcare",
            dedup_key="abc123",
            status="pending",
            triggered_by_user_id=user_id,
        )
        await event_repo.create(event)
        await session.commit()
        print(f"   Created event id={event.id}, domain={event.domain}")

        # ── 3. Repository Filtering ──
        print("\n[3] Repository filtering...")
        filtered = await event_repo.list_with_filters(domain="healthcare", limit=10)
        assert len(filtered) >= 1, "Should find the healthcare event"
        print(f"   Found {len(filtered)} healthcare event(s)")

        # ── 4. Correlation Engine ──
        print("\n[4] Correlation engine cycle...")
        engine = CorrelationEngine(session)
        stats = await engine.run_cycle()
        await session.commit()
        print(f"   Cycle stats: {stats}")
        assert isinstance(stats, dict), "Correlation engine should return stats dict"

        # ── 5. Metrics Recording ──
        print("\n[5] Metric recording...")
        metric_service = EventMetricService(session)
        await metric_service.record_event_created(event)
        event.resolved_at = __import__("datetime").datetime.utcnow()
        await metric_service.record_event_resolved(event)
        await session.commit()

        metrics = await metric_service.get_metrics(domain="healthcare")
        assert len(metrics) >= 1, "Should have recorded metrics"
        print(f"   Recorded metrics: total_events={metrics[0].total_events}")

        # Cleanup
        await _reset_test_data(session, user_id)

        print("\n[OK] All smoke tests passed!")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
