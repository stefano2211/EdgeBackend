from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class EventSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class EventStatus(str, Enum):
    pending = "pending"
    analyzing = "analyzing"
    awaiting_approval = "awaiting_approval"
    executing = "executing"
    completed = "completed"
    failed = "failed"


class EventSourceType(str, Enum):
    sensor = "sensor"
    db_collector = "db_collector"
    manual = "manual"
    webhook = "webhook"


class ManualEventPayload(BaseModel):
    severity: EventSeverity
    title: str
    description: str
    raw_payload: dict | None = None


class EventIngestPayload(BaseModel):
    tenant_id: str = "default"
    source_type: EventSourceType = EventSourceType.sensor
    severity: EventSeverity
    title: str
    description: str
    raw_payload: dict | None = None


class EventOut(BaseModel):
    id: int
    tenant_id: str
    source_type: EventSourceType
    severity: EventSeverity
    status: EventStatus
    title: str
    description: str
    raw_payload: dict | None = None
    agent_analysis: str | None = None
    agent_reasoning: str | None = None
    agent_plan: str | None = None
    actions_taken: list | None = None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    triggered_by_user_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class EventListResponse(BaseModel):
    total: int
    items: list[EventOut]


class ApprovalPayload(BaseModel):
    notes: str | None = None
