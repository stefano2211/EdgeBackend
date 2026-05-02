"""Vector repository — CRUD operations on Qdrant points.

Layer: persistencia/vector (data access layer)
Mirrors the SQLAlchemy BaseRepository pattern for vector data.
"""

import uuid
from typing import Any

from qdrant_client.models import PointStruct

from src.core.logging import logging
from src.persistencia.vector.qdrant_client import (
    get_qdrant_client,
    collection_name,
    ensure_collection,
)

logger = logging.getLogger(__name__)


class VectorRepository:
    """Repository for upserting/searching/deleting document chunks in Qdrant."""

    def __init__(self) -> None:
        self.client = get_qdrant_client()

    # ── Write ────────────────────────────────────────────

    async def upsert_chunks(
        self,
        knowledge_base_id: int | str,
        chunks: list[str],
        embeddings: list[list[float]],
        metadata: dict[str, Any],
        doc_id: int | str,
        chunk_size: int = 1000,
        overlap: int = 200,
    ) -> None:
        """Upsert document chunks into the KB collection."""
        await ensure_collection(knowledge_base_id, dimension=len(embeddings[0]))
        name = collection_name(knowledge_base_id)

        points: list[PointStruct] = []
        for i, (chunk, vector) in enumerate(zip(chunks, embeddings)):
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={
                        "text": chunk,
                        "chunk_index": i,
                        "doc_id": doc_id,
                        **metadata,
                    },
                )
            )

        await self.client.upsert(
            collection_name=name,
            points=points,
            wait=False,  # non-blocking for bulk background inserts
        )
        logger.info(
            "Upserted %d chunks → %s (doc_id=%s)",
            len(points),
            name,
            doc_id,
        )

    # ── Read ─────────────────────────────────────────────

    async def search_chunks(
        self,
        knowledge_base_id: int | str,
        query_embedding: list[float],
        top_k: int = 5,
        filter_doc_ids: list[int | str] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for top-k similar chunks. Optional filter by doc_id list."""
        name = collection_name(knowledge_base_id)

        query_filter = None
        if filter_doc_ids:
            from qdrant_client.models import Filter, FieldCondition, MatchAny
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="doc_id",
                        match=MatchAny(any=[str(d) for d in filter_doc_ids]),
                    )
                ]
            )

        results = await self.client.search(
            collection_name=name,
            query_vector=query_embedding,
            limit=top_k,
            with_payload=True,
            query_filter=query_filter,
        )

        return [
            {
                "id": str(r.id),
                "score": r.score,
                "text": r.payload.get("text", ""),
                "chunk_index": r.payload.get("chunk_index", 0),
                "doc_id": r.payload.get("doc_id"),
                "filename": r.payload.get("filename"),
                "page_number": r.payload.get("page_number"),
            }
            for r in results
        ]

    # ── Delete ───────────────────────────────────────────

    async def delete_by_doc_id(
        self,
        knowledge_base_id: int | str,
        doc_id: int | str,
    ) -> None:
        """Remove all chunks belonging to a single document."""
        name = collection_name(knowledge_base_id)
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        await self.client.delete(
            collection_name=name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="doc_id",
                        match=MatchValue(value=str(doc_id)),
                    )
                ]
            ),
        )
        logger.info("Deleted chunks for doc_id=%s from %s", doc_id, name)
