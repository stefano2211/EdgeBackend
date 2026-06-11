"""Pydantic schemas for the data-analyst-agent service.

These models define the contract between the service layer and the API layer
for natural-language-to-SQL analysis.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# ═══════════════════════════════════════════════════════════════════════
#  Request / Response models for the API
# ═══════════════════════════════════════════════════════════════════════

class AnalystQuestion(BaseModel):
    """User's natural-language question about their data."""
    question: str = Field(..., min_length=1, max_length=2000)
    connection_hint: str | None = Field(
        default=None,
        description="Optional hint: name of a specific connection to use",
    )
    context: str = "chat"  # "chat" | "reactive"
    connection_ids: list[str] | None = Field(
        default=None,
        description="Optional list of connection IDs to restrict the analysis to",
    )


class AnalystResult(BaseModel):
    """Full result of a natural-language data analysis."""
    question: str
    sql: str | None = None
    sql_explanation: str | None = None
    results: QueryOutput | None = None
    insights: str | None = None
    connection_used: str | None = None
    connection_id: str | None = None
    execution_time_ms: int | None = None
    retries: int = 0
    status: str = "success"  # "success" | "partial" | "failed"
    error: str | None = None


class QueryOutput(BaseModel):
    """Structured query output for the frontend to render."""
    columns: list[str] = Field(default_factory=list)
    rows: list[list] = Field(default_factory=list)
    row_count: int = 0
    truncated: bool = False


# ═══════════════════════════════════════════════════════════════════════
#  Internal models (service layer)
# ═══════════════════════════════════════════════════════════════════════

class GeneratedSQL(BaseModel):
    """Result of the NL → SQL generation step."""
    sql: str
    connection_id: str
    connection_name: str
    explanation: str | None = None
    confidence: str = "medium"  # "high" | "medium" | "low"
    targeted_tables: list[str] = Field(default_factory=list)


class SQLExecutionResult(BaseModel):
    """Result after executing SQL (possibly after retries)."""
    final_sql: str
    success: bool
    data: QueryOutput | None = None
    error: str | None = None
    connection_id: str
    connection_name: str
    elapsed_ms: int = 0
    attempts: int = 0


class SchemaContextItem(BaseModel):
    """Single item retrieved from the schema RAG search."""
    connection_id: str
    connection_name: str
    type: str  # "table" | "column"
    table_name: str
    column_name: str | None = None
    description: str = ""
    data_type: str = ""
    is_pk: bool = False
    fk_to: str | None = None
    cardinality: str = "unknown"
    sample_values: list[str] = Field(default_factory=list)
    relevance_score: float = 0.0


class ConnectionSummary(BaseModel):
    """Lightweight summary of a database connection for the agent."""
    id: str
    name: str
    db_type: str
    description: str | None = None
    status: str
    available_in_chat: bool
    available_in_reactive: bool

    model_config = ConfigDict(from_attributes=True)


class DataAnalystError(Exception):
    """Custom exception for data analyst pipeline failures."""
    pass

