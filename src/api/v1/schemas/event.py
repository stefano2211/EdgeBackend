"""Event schemas — CloudEvents + OpenTelemetry compatible.

This module defines the API contract for event ingestion and retrieval.
It supports both CloudEvents-native payloads and legacy generic JSON.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ── Enums ──

class EventSeverityText(str, Enum):
    """Human-readable severity levels."""

    critical = "critical"
    error = "error"
    warning = "warning"
    info = "info"
    debug = "debug"


class EventStatus(str, Enum):
    """Event lifecycle states."""

    pending = "pending"
    analyzing = "analyzing"
    awaiting_approval = "awaiting_approval"
    executing = "executing"
    completed = "completed"
    failed = "failed"
    suppressed = "suppressed"


# ── Severity mapping utilities ──

_SEVERITY_TEXT_TO_NUMBER: dict[str, int] = {
    "debug": 5,
    "info": 9,
    "warning": 13,
    "warn": 13,
    "error": 17,
    "critical": 21,
    "fatal": 24,
}

_SEVERITY_NUMBER_TO_TEXT: dict[int, str] = {
    1: "debug", 2: "debug", 3: "debug", 4: "debug",
    5: "debug", 6: "debug", 7: "debug", 8: "debug",
    9: "info", 10: "info", 11: "info", 12: "info",
    13: "warning", 14: "warning", 15: "warning", 16: "warning",
    17: "error", 18: "error", 19: "error", 20: "error",
    21: "critical", 22: "critical", 23: "critical", 24: "critical",
}


def severity_text_to_number(text: str | None, default: int = 13) -> int:
    if not text:
        return default
    return _SEVERITY_TEXT_TO_NUMBER.get(text.lower(), default)


def severity_number_to_text(number: int | None, default: str = "warning") -> str:
    if number is None:
        return default
    return _SEVERITY_NUMBER_TO_TEXT.get(number, default)


# ── Ingestion payloads ──

class EventIngestPayload(BaseModel):
    """Generic event ingestion payload.

    Supports CloudEvents attributes (specversion, type, source, id, time, subject)
    as well as legacy fields for backward compatibility.
    """

    # CloudEvents core (optional — auto-detected if missing)
    specversion: str = "1.0"
    type: str | None = Field(None, description="CloudEvents type (ce-type)")
    source: str | None = Field(None, description="CloudEvents source (ce-source)")
    id: str | None = Field(None, description="CloudEvents id (ce-id)")
    time: datetime | None = Field(None, description="CloudEvents time (ce-time)")
    subject: str | None = Field(None, description="CloudEvents subject (ce-subject)")

    # OpenTelemetry severity
    severity_number: int | None = Field(None, ge=1, le=24, description="OTel severity 1-24")
    severity_text: EventSeverityText | None = Field(None, description="Human severity")

    # Content
    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = Field(None, max_length=5000)
    data: dict | None = Field(None, description="Event payload body")

    # Legacy compatibility
    tenant_id: str = "default"
    raw_payload: dict | None = Field(None, description="Deprecated: use 'data'")
    source_type: str | None = Field(None, description="Deprecated: use 'source'")

    @model_validator(mode="after")
    def normalize(self) -> "EventIngestPayload":
        # Ensure we have a title
        if not self.title and self.subject:
            self.title = self.subject
        if not self.title and self.type:
            self.title = self.type.replace(".", " ").replace("_", " ").title()

        # Map severity_text -> severity_number if needed
        if self.severity_number is None and self.severity_text:
            self.severity_number = severity_text_to_number(self.severity_text.value)
        elif self.severity_number is not None and self.severity_text is None:
            self.severity_text = EventSeverityText(
                severity_number_to_text(self.severity_number)
            )
        elif self.severity_number is None and self.severity_text is None:
            self.severity_number = 13
            self.severity_text = EventSeverityText.warning

        # data vs raw_payload fallback
        if self.data is None and self.raw_payload is not None:
            self.data = self.raw_payload

        # source vs source_type fallback
        if self.source is None and self.source_type is not None:
            self.source = self.source_type

        return self


class ManualEventPayload(BaseModel):
    """Manual event creation by an authenticated user."""

    severity_text: EventSeverityText = EventSeverityText.warning
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = Field(None, max_length=5000)
    data: dict | None = None


# ── Output schemas ──

class EventOut(BaseModel):
    """Full event representation for API responses."""

    id: int
    event_id: str
    event_type: str
    source: str
    timestamp: datetime
    subject: str | None
    severity_number: int
    severity_text: str
    title: str
    description: str | None
    body: dict | None
    domain: str | None
    subdomain: str | None
    correlation_id: str | None
    dedup_key: str | None
    resource: dict | None
    status: EventStatus
    suppression_reason: str | None
    agent_analysis: str | None
    agent_reasoning: str | None
    agent_plan: str | None
    actions_taken: list | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    triggered_by_user_id: int | None
    correlation_group_id: int | None

    model_config = ConfigDict(from_attributes=True)


class EventListResponse(BaseModel):
    total: int
    items: list[EventOut]


class ApprovalPayload(BaseModel):
    notes: str | None = None


class EventFeedbackPayload(BaseModel):
    feedback_type: str = Field(..., pattern="^(false_positive|incorrect_diagnosis|wrong_severity|other)$")
    comment: str | None = None
