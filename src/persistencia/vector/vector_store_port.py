"""Vector store port (protocol) for dependency inversion.

The domain/services layer should depend on this abstraction rather than
the concrete VectorRepository/Qdrant implementation.

Supports hybrid search (dense + sparse vectors) and named vector architecture.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Any


@dataclass(frozen=True, slots=True)
class SparseVector:
    """Sparse vector representation for BM25/IDF-based search."""

    indices: list[int]
    values: list[float]


class VectorStorePort(Protocol):
    """Protocol for vector store operations with hybrid search support."""

    async def upsert_chunks(
        self,
        knowledge_base_id: int | str,
        chunks: list[str],
        embeddings: list[list[float]],
        metadata: list[dict[str, Any]] | dict[str, Any],
        doc_id: int | str,
        sparse_embeddings: list[SparseVector] | None = None,
    ) -> None:
        ...

    async def search_chunks(
        self,
        knowledge_base_id: int | str,
        query_embedding: list[float],
        top_k: int = 5,
        filter_doc_ids: list[int | str] | None = None,
        hnsw_ef: int = 128,
        sparse_query: SparseVector | None = None,
        prefetch_limit: int = 50,
    ) -> list[dict[str, Any]]:
        ...

    async def delete_by_doc_id(
        self,
        knowledge_base_id: int | str,
        doc_id: int | str,
    ) -> None:
        ...

    async def delete_collection(
        self,
        knowledge_base_id: int | str,
    ) -> None:
        ...
