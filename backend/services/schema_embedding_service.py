"""Schema embedding service — indexes and searches database schemas via semantic RAG.

High-level service that:
  1. Converts discovered schema (tables/columns) into searchable text snippets.
  2. Generates dense + sparse embeddings.
  3. Upserts into Qdrant collection "schema_embeddings".
  4. Performs semantic search to retrieve only relevant schema items for a NL question.

Usage:
    service = SchemaEmbeddingService()
    await service.index_schema(connection_id, schema_result)
    relevant = await service.search_relevant_schema(user_id, "productos mas vendidos")
"""

from __future__ import annotations

from typing import Any

from backend.core.config import settings
from backend.core.logging import logging
from backend.database_connector.schemas import SchemaDiscoveryResult, SchemaTable, SchemaColumn
from backend.persistencia.vector.schema_vector_repository import SchemaVectorRepository
from backend.services.embedding_service import embed_texts, embed_query
from backend.services.sparse_embedding_service import embed_sparse_texts, embed_sparse_query

logger = logging.getLogger(__name__)


class SchemaEmbeddingService:
    """Service for indexing and retrieving database schema via semantic search."""

    def __init__(self, vector_repo: SchemaVectorRepository | None = None) -> None:
        self.vector_repo = vector_repo or SchemaVectorRepository()

    # ═══════════════════════════════════════════════════════════════════════
    #  INDEXING
    # ═══════════════════════════════════════════════════════════════════════

    async def index_schema(
        self,
        connection_id: str,
        connection_name: str,
        user_id: int,
        schema: SchemaDiscoveryResult,
    ) -> None:
        """Index all tables and columns from a schema discovery result.

        This should be called after discover_schema() succeeds.
        It first deletes old items for this connection, then re-indexes.
        """
        # 1. Delete stale schema items for this connection
        try:
            await self.vector_repo.delete_by_connection(connection_id)
        except Exception as exc:
            logger.warning("Failed to delete old schema index for %s: %s", connection_id, exc)

        # 2. Build text snippets and metadata items
        items: list[dict[str, Any]] = []
        texts: list[str] = []

        for table in schema.tables:
            # Table-level item
            table_text = self._build_table_text(table)
            items.append(self._build_table_item(table))
            texts.append(table_text)

            # Column-level items
            for col in table.columns:
                col_text = self._build_column_text(table.name, col)
                items.append(self._build_column_item(table.name, col))
                texts.append(col_text)

        if not texts:
            logger.info("No schema items to index for connection=%s", connection_id)
            return

        # 3. Generate embeddings
        dense_embeddings = await embed_texts(texts, batch_size=64)
        sparse_embeddings = None
        if settings.HYBRID_SEARCH_ENABLED:
            try:
                sparse_embeddings = await embed_sparse_texts(texts)
            except Exception as exc:
                logger.warning("Sparse schema embedding failed: %s", exc)

        # 4. Upsert to Qdrant
        await self.vector_repo.upsert_schema_items(
            connection_id=connection_id,
            connection_name=connection_name,
            user_id=user_id,
            items=items,
            dense_embeddings=dense_embeddings,
            sparse_embeddings=sparse_embeddings,
        )

    # ═══════════════════════════════════════════════════════════════════════
    #  SEARCH
    # ═══════════════════════════════════════════════════════════════════════

    async def search_relevant_schema(
        self,
        user_id: int,
        question: str,
        connection_ids: list[str] | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Find schema items (tables/columns) relevant to a natural-language question.

        Args:
            user_id: Owner of the schema.
            question: Natural language question (e.g. "productos mas vendidos").
            connection_ids: Optional list of connection UUIDs to scope the search.
            top_k: Number of top results to return.

        Returns:
            List of payload dicts with keys: connection_id, connection_name,
            type, table_name, column_name, description, data_type, is_pk,
            fk_to, cardinality, sample_values, score.
        """
        # 1. Embed the question
        dense_embedding = await embed_query(question, use_cache=True)
        sparse_embedding = None
        if settings.HYBRID_SEARCH_ENABLED:
            try:
                sparse_embedding = await embed_sparse_query(question)
            except Exception as exc:
                logger.debug("Sparse query embedding failed: %s", exc)

        # 2. Search Qdrant
        results = await self.vector_repo.search_relevant_items(
            user_id=user_id,
            query_embedding=dense_embedding,
            top_k=top_k,
            connection_ids=connection_ids,
            sparse_query=sparse_embedding,
        )

        logger.info(
            "Schema search: user=%s question='%s...' results=%d",
            user_id,
            question[:50],
            len(results),
        )
        return results

    # ═══════════════════════════════════════════════════════════════════════
    #  CLEANUP
    # ═══════════════════════════════════════════════════════════════════════

    async def delete_schema_index(self, connection_id: str) -> None:
        """Remove all indexed schema items for a connection (e.g. on deletion)."""
        await self.vector_repo.delete_by_connection(connection_id)

    # ═══════════════════════════════════════════════════════════════════════
    #  TEXT BUILDERS (determine semantic search quality)
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _build_table_text(table: SchemaTable) -> str:
        """Build a rich text snippet for a table."""
        parts = [f"Tabla {table.name}"]
        if table.description:
            parts.append(f": {table.description}")
        if table.row_count is not None:
            parts.append(f". Contiene aproximadamente {table.row_count} filas.")
        parts.append(f" Tiene {len(table.columns)} columnas.")
        # Include column names for context
        col_names = [c.name for c in table.columns]
        parts.append(f" Columnas: {', '.join(col_names)}.")
        return "".join(parts)

    @staticmethod
    def _build_column_text(table_name: str, col: SchemaColumn) -> str:
        """Build a rich text snippet for a column."""
        parts = [f"Columna {col.name} en tabla {table_name}"]
        if col.description:
            parts.append(f": {col.description}")
        parts.append(f". Tipo de dato: {col.type}.")
        if col.is_pk:
            parts.append(" Es clave primaria.")
        if col.fk_ref:
            parts.append(f" Es clave foránea que referencia a {col.fk_ref}.")
        if hasattr(col, "cardinality") and col.cardinality != "unknown":
            parts.append(f" Cardinalidad: {col.cardinality}.")
        # Sample values give semantic hints
        if hasattr(col, "sample_values") and col.sample_values:
            samples = ", ".join(str(v) for v in col.sample_values[:5])
            parts.append(f" Ejemplos de valores: {samples}.")
        return "".join(parts)

    @staticmethod
    def _build_table_item(table: SchemaTable) -> dict[str, Any]:
        return {
            "type": "table",
            "table_name": table.name,
            "column_name": None,
            "description": table.description,
            "data_type": "table",
            "is_pk": False,
            "fk_to": None,
            "cardinality": "n/a",
            "sample_values": [],
        }

    @staticmethod
    def _build_column_item(table_name: str, col: SchemaColumn) -> dict[str, Any]:
        return {
            "type": "column",
            "table_name": table_name,
            "column_name": col.name,
            "description": col.description,
            "data_type": col.type,
            "is_pk": col.is_pk,
            "fk_to": col.fk_ref,
            "cardinality": getattr(col, "cardinality", "unknown"),
            "sample_values": getattr(col, "sample_values", []),
        }
