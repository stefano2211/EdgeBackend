"""Vector repository — CRUD operations on Qdrant points with hybrid search.

Layer: persistencia/vector (data access layer)
Mirrors the SQLAlchemy BaseRepository pattern for vector data.

2026 Qdrant best practices applied:
- Named vectors (dense + sparse) for hybrid retrieval
- RRF (Reciprocal Rank Fusion) via Qdrant native Query API
- Payload indexes for doc_id and filename (fast filtering + deletion)
- SearchParams with tuned hnsw_ef for recall/speed balance
- Per-chunk metadata preserved in each PointStruct
- Batch upsert with wait=False for background ingestion
"""

from __future__ import annotations

import uuid
from typing import Any

from qdrant_client import models
from qdrant_client.models import PointStruct, SearchParams

from backend.core.config import settings
from backend.core.logging import logging
from backend.persistencia.vector.qdrant_client import (
    get_qdrant_client,
    collection_name,
    ensure_collection,
)
from backend.persistencia.vector.vector_store_port import SparseVector

logger = logging.getLogger(__name__)


class VectorRepository:
    """Repository for upserting/searching/deleting document chunks in Qdrant.

    Supports hybrid search with dense + sparse named vectors and RRF fusion.
    """

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
        sparse_embeddings: list[SparseVector] | None = None,
        prefix: str = "kb_",
        context: list[str] | None = None,
    ) -> None:
        """Upsert document chunks with dense + sparse vectors into the KB collection.

        Args:
            chunks: List of chunk texts.
            embeddings: Dense embeddings (parallel to chunks).
            metadata: Per-chunk metadata list or a single dict applied to all.
            doc_id: Source document ID for filtering/deletion.
            sparse_embeddings: Optional sparse BM25 vectors (parallel to chunks).
            prefix: Collection name prefix (default "kb_", use "reactive_kb_" for reactive).
            context: Optional list of context tags (e.g. ["chat"], ["reactive"], ["chat", "reactive"]).
        """
        await ensure_collection(knowledge_base_id, dimension=len(embeddings[0]), prefix=prefix)
        name = collection_name(knowledge_base_id, prefix=prefix)

        # Ensure metadata is per-chunk
        if isinstance(metadata, dict):
            meta_list: list[dict] = [metadata.copy() for _ in chunks]
        else:
            meta_list = list(metadata)
            if len(meta_list) < len(chunks):
                meta_list += [{}] * (len(chunks) - len(meta_list))

        points: list[PointStruct] = []
        for i, (chunk_text, dense_vec, meta) in enumerate(
            zip(chunks, embeddings, meta_list)
        ):
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

            # Inject context tags for per-context retrieval
            if context:
                payload["context"] = context

            # Build named vector dict
            vector: dict[str, Any] = {"dense": dense_vec}
            if sparse_embeddings is not None and i < len(sparse_embeddings):
                sv = sparse_embeddings[i]
                vector["sparse"] = models.SparseVector(
                    indices=sv.indices,
                    values=sv.values,
                )

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
            "Upserted %d chunks → %s (doc_id=%s, sparse=%s)",
            len(points),
            name,
            doc_id,
            sparse_embeddings is not None,
        )

    # ── Read ─────────────────────────────────────────────

    async def search_chunks(
        self,
        knowledge_base_id: int | str,
        query_embedding: list[float],
        top_k: int = 5,
        filter_doc_ids: list[int | str] | None = None,
        hnsw_ef: int = 128,
        sparse_query: SparseVector | None = None,
        prefetch_limit: int = 50,
        prefix: str = "kb_",
        context: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for top-k similar chunks using hybrid search (dense + sparse + RRF).

        When sparse_query is provided, performs a two-stage hybrid search:
        1. Prefetch top-N from dense vector space
        2. Prefetch top-N from sparse (BM25) vector space
        3. Fuse results using Reciprocal Rank Fusion (RRF)

        Falls back to dense-only search when sparse_query is None.

        Args:
            query_embedding: Dense query vector (all-MiniLM-L6-v2).
            top_k: Number of final results to return.
            filter_doc_ids: Optional filter to specific documents.
            hnsw_ef: HNSW exploration factor (64-128 sweet spot).
            sparse_query: Optional sparse BM25 query vector.
            prefetch_limit: Number of candidates per prefetch stage.
            prefix: Collection name prefix (default "kb_", use "reactive_kb_" for reactive).
            context: Optional context tag to filter chunks ("chat" or "reactive").
        """
        name = collection_name(knowledge_base_id, prefix=prefix)

        # Build optional filter
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

        if context:
            from qdrant_client.models import Filter, FieldCondition, MatchAny

            context_filter = FieldCondition(
                key="context",
                match=MatchAny(any=[context]),
            )
            if query_filter is None:
                query_filter = Filter(must=[context_filter])
            else:
                query_filter.must.append(context_filter)

        search_params = SearchParams(hnsw_ef=hnsw_ef, exact=False)

        # ── Hybrid search with RRF fusion ──
        if sparse_query is not None and settings.HYBRID_SEARCH_ENABLED:
            response = await self.client.query_points(
                collection_name=name,
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
                "Hybrid RRF search on %s: prefetch=%d, final=%d results",
                name,
                prefetch_limit,
                len(response.points),
            )
        else:
            # ── Dense-only fallback ──
            response = await self.client.query_points(
                collection_name=name,
                query=query_embedding,
                using="dense",
                limit=top_k,
                with_payload=True,
                query_filter=query_filter,
                search_params=search_params,
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
        prefix: str = "kb_",
    ) -> None:
        """Remove all chunks belonging to a single document."""
        name = collection_name(knowledge_base_id, prefix=prefix)
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

    async def delete_collection(
        self, knowledge_base_id: int | str, prefix: str = "kb_"
    ) -> None:
        """Remove an entire Qdrant collection for a knowledge base."""
        name = collection_name(knowledge_base_id, prefix=prefix)
        await self.client.delete_collection(collection_name=name)
        logger.info("Deleted Qdrant collection %s", name)
