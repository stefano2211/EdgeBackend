"""Schema vector repository — CRUD for database schema embeddings in Qdrant.

Layer: persistencia/vector (data access layer)
Mirrors the VectorRepository pattern but specialised for schema items
(tables and columns) with a dedicated collection.

Collection: schema_embeddings (named vectors: dense + sparse)
"""

from __future__ import annotations

import uuid
from typing import Any

from qdrant_client import models
from qdrant_client.models import PointStruct, SearchParams

from backend.core.config import settings
from backend.core.logging import logging
from backend.infrastructure.vector.qdrant_client import (
    get_qdrant_client,
    ensure_collection,
    collection_name,
)
from backend.infrastructure.vector.vector_store_port import SparseVector

logger = logging.getLogger(__name__)

_SCHEMA_COLLECTION = "schema_embeddings"
_SCHEMA_DIMENSION = 384  # all-MiniLM-L6-v2

# UUID v5 namespace for deterministic point IDs from composite keys
_SCHEMA_UUID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # DNS namespace


class SchemaVectorRepository:
    """Repository for upserting/searching schema items (tables/columns) in Qdrant.

    Each schema item (table or column) becomes a point in the vector space,
    allowing semantic search to find relevant tables/columns for a user question.
    """

    def __init__(self) -> None:
        self.client = get_qdrant_client()

    # ── Write ────────────────────────────────────────────

    async def upsert_schema_items(
        self,
        connection_id: str,
        connection_name: str,
        user_id: int,
        items: list[dict[str, Any]],
        dense_embeddings: list[list[float]],
        sparse_embeddings: list[SparseVector] | None = None,
    ) -> None:
        """Upsert schema table/column items with dense + sparse vectors.

        Args:
            connection_id: UUID of the DatabaseConnection.
            connection_name: Human-readable connection name (e.g. "produccion_postgres").
            user_id: Owner user ID (used for filtering searches).
            items: List of dicts with keys:
                - type: "table" | "column"
                - table_name: str
                - column_name: str | None
                - description: str | None
                - data_type: str
                - is_pk: bool
                - fk_to: str | None
                - cardinality: str
                - sample_values: list[str] | None
            dense_embeddings: One dense vector per item (parallel).
            sparse_embeddings: One sparse vector per item (parallel), optional.
        """
        if len(items) != len(dense_embeddings):
            raise ValueError(
                f"items ({len(items)}) and dense_embeddings ({len(dense_embeddings)}) must be parallel"
            )
        if sparse_embeddings is not None and len(items) != len(sparse_embeddings):
            raise ValueError(
                f"items ({len(items)}) and sparse_embeddings ({len(sparse_embeddings)}) must be parallel"
            )

        await ensure_collection(
            _SCHEMA_COLLECTION,
            dimension=_SCHEMA_DIMENSION,
            prefix="",  # collection name is literal, no prefix
        )

        points: list[PointStruct] = []
        for i, (item, dense_vec) in enumerate(zip(items, dense_embeddings)):
            payload = {
                "connection_id": connection_id,
                "connection_name": connection_name,
                "user_id": user_id,
                "type": item["type"],
                "table_name": item["table_name"],
                "column_name": item.get("column_name"),
                "description": item.get("description") or "",
                "data_type": item.get("data_type", ""),
                "is_pk": item.get("is_pk", False),
                "fk_to": item.get("fk_to"),
                "cardinality": item.get("cardinality", "unknown"),
                "sample_values": item.get("sample_values", []),
            }

            vector: dict[str, Any] = {"dense": dense_vec}
            if sparse_embeddings is not None and i < len(sparse_embeddings):
                sv = sparse_embeddings[i]
                vector["sparse"] = models.SparseVector(
                    indices=sv.indices,
                    values=sv.values,
                )

            point_id = str(uuid.uuid5(_SCHEMA_UUID_NAMESPACE, f"{connection_id}:{item['table_name']}:{item.get('column_name') or ''}"))
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            )

        await self.client.upsert(
            collection_name=_SCHEMA_COLLECTION,
            points=points,
            wait=False,
        )
        logger.info(
            "Upserted %d schema items → %s (connection=%s)",
            len(points),
            _SCHEMA_COLLECTION,
            connection_id,
        )

    # ── Read ─────────────────────────────────────────────

    async def search_relevant_items(
        self,
        user_id: int,
        query_embedding: list[float],
        top_k: int = 10,
        connection_ids: list[str] | None = None,
        hnsw_ef: int = 128,
        sparse_query: SparseVector | None = None,
        prefetch_limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Search for top-k relevant schema items for a given question embedding.

        Uses hybrid search (dense + sparse + RRF) when sparse_query is provided,
        otherwise dense-only fallback.

        Args:
            user_id: Filter to schemas owned by this user.
            query_embedding: Dense query vector (all-MiniLM-L6-v2).
            top_k: Number of final results.
            connection_ids: Optional filter to specific connections.
            hnsw_ef: HNSW exploration factor.
            sparse_query: Optional sparse BM25 query vector.
            prefetch_limit: Candidates per prefetch stage.
        """
        from qdrant_client.models import Filter, FieldCondition, MatchAny, MatchValue

        # Build user_id filter + optional connection_id filter
        must_conditions = [
            FieldCondition(key="user_id", match=MatchValue(value=user_id))
        ]
        if connection_ids:
            must_conditions.append(
                FieldCondition(
                    key="connection_id",
                    match=MatchAny(any=connection_ids),
                )
            )

        query_filter = Filter(must=must_conditions)
        search_params = SearchParams(hnsw_ef=hnsw_ef, exact=False)

        try:
            # ── Hybrid search with RRF ──
            if sparse_query is not None and settings.HYBRID_SEARCH_ENABLED:
                response = await self.client.query_points(
                    collection_name=_SCHEMA_COLLECTION,
                    prefetch=[
                        models.Prefetch(
                            query=query_embedding,
                            using="dense",
                            limit=prefetch_limit,
                            filter=query_filter,
                            params=search_params,
                        ),
                        models.Prefetch(
                            query=models.SparseVector(
                                indices=sparse_query.indices,
                                values=sparse_query.values,
                            ),
                            using="sparse",
                            limit=prefetch_limit,
                            filter=query_filter,
                        ),
                    ],
                    query=models.FusionQuery(fusion=models.Fusion.RRF),
                    limit=top_k,
                    with_payload=True,
                )
                logger.debug(
                    "Schema hybrid RRF search: user=%s, top_k=%d, results=%d",
                    user_id,
                    top_k,
                    len(response.points),
                )
            else:
                # ── Dense-only fallback ──
                response = await self.client.query_points(
                    collection_name=_SCHEMA_COLLECTION,
                    query=query_embedding,
                    using="dense",
                    limit=top_k,
                    with_payload=True,
                    query_filter=query_filter,
                    search_params=search_params,
                )
        except Exception as exc:
            if "not found" in str(exc).lower() or "404" in str(exc).lower():
                logger.warning(
                    "Qdrant collection %s does not exist yet. Returning empty schema results.",
                    _SCHEMA_COLLECTION,
                )
                return []
            raise

        return [
            {
                "id": str(r.id),
                "score": r.score,
                "connection_id": r.payload.get("connection_id"),
                "connection_name": r.payload.get("connection_name"),
                "type": r.payload.get("type"),
                "table_name": r.payload.get("table_name"),
                "column_name": r.payload.get("column_name"),
                "description": r.payload.get("description"),
                "data_type": r.payload.get("data_type"),
                "is_pk": r.payload.get("is_pk"),
                "fk_to": r.payload.get("fk_to"),
                "cardinality": r.payload.get("cardinality"),
                "sample_values": r.payload.get("sample_values", []),
            }
            for r in response.points
        ]

    # ── Delete ───────────────────────────────────────────

    async def delete_by_connection(self, connection_id: str) -> None:
        """Remove all schema items belonging to a single connection."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        await self.client.delete(
            collection_name=_SCHEMA_COLLECTION,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="connection_id",
                        match=MatchValue(value=connection_id),
                    )
                ]
            ),
        )
        logger.info(
            "Deleted schema items for connection=%s from %s",
            connection_id,
            _SCHEMA_COLLECTION,
        )

    async def delete_collection(self) -> None:
        """Remove the entire schema_embeddings collection (destructive)."""
        await self.client.delete_collection(collection_name=_SCHEMA_COLLECTION)
        logger.info("Deleted Qdrant collection %s", _SCHEMA_COLLECTION)
