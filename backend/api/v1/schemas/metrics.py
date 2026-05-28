"""Metrics schemas."""

from pydantic import BaseModel


class MetricsResponse(BaseModel):
    total_events: int
    events_analyzed: int
    events_auto_resolved: int
    events_failed: int
    false_positives: int
    false_positive_rate: float
    avg_ttd_seconds: float | None
    avg_ttr_seconds: float | None


class MetricsSummary(BaseModel):
    total_events_last_7d: int
    false_positive_rate: float
