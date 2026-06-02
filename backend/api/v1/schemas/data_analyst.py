"""Pydantic schemas for the data-analyst REST API.

These wrap the service-layer schemas for HTTP serialization.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DataAnalystAskRequest(BaseModel):
    """POST /data-analyst/ask"""
    question: str = Field(..., min_length=1, max_length=2000)
    connection_hint: str | None = Field(
        default=None,
        description="Optional: name of a specific DB connection to use",
    )
    context: str = "chat"  # "chat" | "reactive"


class QueryOutput(BaseModel):
    columns: list[str] = Field(default_factory=list)
    rows: list[list] = Field(default_factory=list)
    row_count: int = 0
    truncated: bool = False


class DataAnalystAskResponse(BaseModel):
    question: str
    sql: str | None = None
    sql_explanation: str | None = None
    results: QueryOutput | None = None
    insights: str | None = None
    connection_used: str | None = None
    connection_id: str | None = None
    execution_time_ms: int | None = None
    retries: int = 0
    status: str = "success"
    error: str | None = None


class ConnectionSummary(BaseModel):
    id: str
    name: str
    db_type: str
    description: str | None = None
    status: str


class SchemaItem(BaseModel):
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
    relevance_score: float = 0.0


class DataAnalystSchemaResponse(BaseModel):
    question: str
    items: list[SchemaItem]


class SQLExplainRequest(BaseModel):
    sql: str = Field(..., min_length=1)
    connection_id: str | None = None


class SQLExplainResponse(BaseModel):
    sql: str
    explanation: str


class TableDescriptionUpdateRequest(BaseModel):
    description: str | None = None


class ColumnDescriptionUpdateRequest(BaseModel):
    description: str | None = None
