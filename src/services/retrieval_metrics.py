"""Retrieval pipeline metrics and observability.

Structured data classes for tracking per-stage latency, hit counts,
and quality scores across the multi-stage retrieval pipeline.

Used by RetrievalPipeline to emit structured logs for monitoring
and debugging RAG quality in production.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from src.core.logging import logging

logger = logging.getLogger(__name__)


@dataclass
class StageMetrics:
    """Metrics for a single pipeline stage."""

    name: str
    latency_ms: float = 0.0
    input_count: int = 0
    output_count: int = 0
    best_score: float = 0.0
    worst_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "latency_ms": round(self.latency_ms, 2),
            "input_count": self.input_count,
            "output_count": self.output_count,
            "best_score": round(self.best_score, 4),
            "worst_score": round(self.worst_score, 4),
        }


@dataclass
class RetrievalMetrics:
    """Aggregated metrics for the full retrieval pipeline."""

    query: str = ""
    total_latency_ms: float = 0.0
    stages: list[StageMetrics] = field(default_factory=list)
    enhanced_queries_count: int = 0
    final_chunk_count: int = 0
    hit: bool = False  # True if we returned any relevant context

    def add_stage(self, stage: StageMetrics) -> None:
        self.stages.append(stage)
        self.total_latency_ms += stage.latency_ms

    def to_dict(self) -> dict:
        return {
            "query": self.query[:100],
            "total_latency_ms": round(self.total_latency_ms, 2),
            "enhanced_queries_count": self.enhanced_queries_count,
            "final_chunk_count": self.final_chunk_count,
            "hit": self.hit,
            "stages": [s.to_dict() for s in self.stages],
        }

    def log_summary(self) -> None:
        """Emit a structured log with pipeline performance summary."""
        logger.info(
            "RAG Pipeline | hit=%s | chunks=%d | latency=%.0fms | stages=%s",
            self.hit,
            self.final_chunk_count,
            self.total_latency_ms,
            " → ".join(
                f"{s.name}({s.output_count}, {s.latency_ms:.0f}ms)"
                for s in self.stages
            ),
        )


class StageTimer:
    """Context manager for timing pipeline stages."""

    def __init__(self, name: str, metrics: RetrievalMetrics):
        self.name = name
        self.metrics = metrics
        self._stage = StageMetrics(name=name)
        self._start = 0.0

    def __enter__(self) -> StageMetrics:
        self._start = time.perf_counter()
        return self._stage

    def __exit__(self, *_) -> None:
        self._stage.latency_ms = (time.perf_counter() - self._start) * 1000
        self.metrics.add_stage(self._stage)
