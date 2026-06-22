"""Data Analyst router — REST endpoints for the data-analyst-agent.

Provides:
  - POST /ask          : Natural-language question → SQL + results + insights
  - GET /connections   : List available DB connections
  - POST /schema       : Retrieve relevant schema items for a question
  - POST /explain      : Explain a SQL query in plain Spanish
  - PATCH /schema/{connection_id}/tables/{table_name}
                       : Update table description
  - PATCH /schema/{connection_id}/columns/{column_name}
                       : Update column description
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.presentation.schemas.data_analyst import (
    DataAnalystAskRequest,
    DataAnalystAskResponse,
    ConnectionSummary,
    SchemaItem,
    DataAnalystSchemaResponse,
    SQLExplainRequest,
    SQLExplainResponse,
    TableDescriptionUpdateRequest,
    ColumnDescriptionUpdateRequest,
)
from backend.core.deps import get_db, get_current_user
from backend.core.exceptions import NotFoundError
from backend.domain.models.user import User
from backend.application.data_analysis.service import DataAnalystService
from backend.application.data_analysis.schemas import AnalystQuestion, ConnectionSummary as ServiceConnectionSummary
from backend.infrastructure.embeddings.schema_embeddings import SchemaEmbeddingService

router = APIRouter(prefix="/data-analyst", tags=["data-analyst"])

logger = logging.getLogger(__name__)


# ── Ask (main endpoint) ───────────────────────────────────────────────

@router.post("/ask", response_model=DataAnalystAskResponse)
async def ask_question(
    data: DataAnalystAskRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DataAnalystAskResponse:
    """Ask a natural-language question about your connected databases.

    Returns the generated SQL, query results, and AI-generated insights.
    """
    service = DataAnalystService(session)
    result = await service.ask(
        AnalystQuestion(
            question=data.question,
            connection_hint=data.connection_hint,
            context=data.context,
        ),
        user_id=current_user.id,
    )

    return DataAnalystAskResponse(
        question=result.question,
        sql=result.sql,
        sql_explanation=result.sql_explanation,
        results=result.results,
        insights=result.insights,
        connection_used=result.connection_used,
        connection_id=result.connection_id,
        execution_time_ms=result.execution_time_ms,
        retries=result.retries,
        status=result.status,
        error=result.error,
    )


# ── Connections ───────────────────────────────────────────────────────

@router.get("/connections", response_model=list[ConnectionSummary])
async def list_connections(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[ConnectionSummary]:
    """List database connections available to the current user."""
    service = DataAnalystService(session)
    conns = await service._get_available_connections(
        user_id=current_user.id,
        context="chat",
    )
    return [
        ConnectionSummary(
            id=c.id,
            name=c.name,
            db_type=c.db_type,
            description=c.description,
            status=c.status,
        )
        for c in conns
    ]


# ── Schema (semantic search) ────────────────────────────────────────────

@router.post("/schema", response_model=DataAnalystSchemaResponse)
async def get_relevant_schema(
    data: DataAnalystAskRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DataAnalystSchemaResponse:
    """Search for schema tables/columns relevant to a natural-language question.

    Uses semantic (vector) search to find the most pertinent schema items.
    """
    service = DataAnalystService(session)

    # Resolve connection hint to IDs if provided
    connection_ids: list[str] | None = None
    if data.connection_hint:
        conns = await service._get_available_connections(current_user.id, data.context)
        matched = [c for c in conns if data.connection_hint.lower() in c.name.lower()]
        if matched:
            connection_ids = [c.id for c in matched]

    items = await service._retrieve_relevant_schema(
        user_id=current_user.id,
        question=data.question,
        connection_ids=connection_ids,
        top_k=15,
    )

    return DataAnalystSchemaResponse(
        question=data.question,
        items=[
            SchemaItem(
                connection_id=i.connection_id,
                connection_name=i.connection_name,
                type=i.type,
                table_name=i.table_name,
                column_name=i.column_name,
                description=i.description or "",
                data_type=i.data_type,
                is_pk=i.is_pk,
                fk_to=i.fk_to,
                cardinality=i.cardinality,
                relevance_score=i.relevance_score,
            )
            for i in items
        ],
    )


# ── Explain SQL ────────────────────────────────────────────────────────

@router.post("/explain", response_model=SQLExplainResponse)
async def explain_sql(
    data: SQLExplainRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SQLExplainResponse:
    """Explain what a SQL query does in plain Spanish."""
    service = DataAnalystService(session)
    explanation = await service.explain_sql(
        sql=data.sql,
        connection_id=data.connection_id or "",
        user_id=current_user.id,
    )
    return SQLExplainResponse(sql=data.sql, explanation=explanation)


# ── Schema Enrichment (table descriptions) ────────────────────────────

@router.patch(
    "/schema/{connection_id}/tables/{table_name}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_table_description(
    connection_id: str,
    table_name: str,
    data: TableDescriptionUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Update the description of a table in the discovered schema.

    This improves the quality of NL2SQL by giving the AI better context.
    """
    from backend.application.data_analysis.connector import DatabaseConnectionService

    db_service = DatabaseConnectionService(session)
    conn = await db_service.get_connection(connection_id, current_user.id)
    if not conn:
        raise NotFoundError("Connection not found")

    current = conn.discovered_schema or {"tables": []}
    for t in current.get("tables", []):
        if t.get("name") == table_name:
            t["description"] = data.description
            break

    conn.discovered_schema = current
    await session.commit()

    # Re-index schema so semantic search uses the new description
    try:
        embedding_svc = SchemaEmbeddingService()
        await embedding_svc.index_schema(
            connection_id=conn.id,
            connection_name=conn.name,
            user_id=conn.user_id,
            schema=SchemaDiscoveryResult(**current),
        )
    except Exception as exc:
        logger.warning("Schema re-index failed after table enrichment: %s", exc)


# ── Schema Enrichment (column descriptions) ────────────────────────────

@router.patch(
    "/schema/{connection_id}/columns/{column_name}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_column_description(
    connection_id: str,
    column_name: str,
    data: ColumnDescriptionUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Update the description of a column in the discovered schema.

    This improves the quality of NL2SQL by giving the AI better context.
    """
    from backend.application.data_analysis.connector import DatabaseConnectionService
    from backend.application.data_analysis.connector_schemas import SchemaDiscoveryResult

    db_service = DatabaseConnectionService(session)
    conn = await db_service.get_connection(connection_id, current_user.id)
    if not conn:
        raise NotFoundError("Connection not found")

    current = conn.discovered_schema or {"tables": []}
    for t in current.get("tables", []):
        for c in t.get("columns", []):
            if c.get("name") == column_name:
                c["description"] = data.description
                break

    conn.discovered_schema = current
    await session.commit()

    # Re-index schema so semantic search uses the new description
    try:
        embedding_svc = SchemaEmbeddingService()
        await embedding_svc.index_schema(
            connection_id=conn.id,
            connection_name=conn.name,
            user_id=conn.user_id,
            schema=SchemaDiscoveryResult(**current),
        )
    except Exception as exc:
        logger.warning("Schema re-index failed after column enrichment: %s", exc)
