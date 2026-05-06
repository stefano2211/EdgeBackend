"""Vector repository — CRUD operations on Qdrant points.

Layer: persistencia/vector (data access layer)
Mirrors the SQLAlchemy BaseRepository pattern for vector data.

2026 Qdrant best practices applied:
- Payload indexes for doc_id and filename (fast filtering + deletion)
- SearchParams with tuned hnsw_ef for recall/speed balance
- Per-chunk metadata preserved in each PointStruct
- Batch upsert with wait=False for background ingestion
"""

from __future__ import annotations

import uuid
from typing import Any

from qdrant_client.models import PointStruct, SearchParams

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
        metadata: list[dict[str, Any]] | dict[str, Any],
        doc_id: int | str,
    ) -> None:
        """Upsert document chunks into the KB collection.

        Args:
            metadata: Per-chunk metadata list (parallel to chunks) OR a single
                dict applied to every chunk (legacy fallback).
        """
        await ensure_collection(knowledge_base_id, dimension=len(embeddings[0]))
        name = collection_name(knowledge_base_id)

        # Ensure metadata is per-chunk
        if isinstance(metadata, dict):
            meta_list: list[dict] = [metadata] * len(chunks)
        else:
            meta_list = list(metadata)
            if len(meta_list) < len(chunks):
                meta_list += [{}] * (len(chunks) - len(meta_list))

        points: list[PointStruct] = []
        for i, (chunk_text, vector, meta) in enumerate(zip(chunks, embeddings, meta_list)):
            payload = {
                "text": chunk_text,
                "chunk_index": i,
                "doc_id": str(doc_id),
                "filename": meta.get("filename", ""),
                **meta,
            }
            # Ensure page_number travels if present
            if "page_number" in meta and meta["page_number"] is not None:
                payload["page_number"] = meta["page_number"]

            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload=payload,
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
        hnsw_ef: int = 128,
    ) -> list[dict[str, Any]]:
        """Search for top-k similar chunks. Optional filter by doc_id list.

        Args:
            hnsw_ef: HNSW exploration factor. Higher = better recall, slower.
                64-128 is the sweet spot for ~10k-100k chunks per collection.
        """
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

        response = await self.client.query_points(
            collection_name=name,
            query=query_embedding,
            limit=top_k,
            with_payload=True,
            query_filter=query_filter,
            search_params=SearchParams(hnsw_ef=hnsw_ef, exact=False),
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
            for r in response.points
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

    async def delete_collection(self, knowledge_base_id: int | str) -> None:
        """Remove an entire Qdrant collection for a knowledge base."""
        name = collection_name(knowledge_base_id)
        await self.client.delete_collection(collection_name=name)
        logger.info("Deleted Qdrant collection %s", name)
