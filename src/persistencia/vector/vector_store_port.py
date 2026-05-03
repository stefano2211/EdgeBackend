"""Vector store port (protocol) for dependency inversion.

The domain/services layer should depend on this abstraction rather than
the concrete VectorRepository/Qdrant implementation.
"""

from typing import Protocol, Any


class VectorStorePort(Protocol):
    """Protocol for vector store operations."""

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
        ...

    async def search_chunks(
        self,
        knowledge_base_id: int | str,
        query_embedding: list[float],
        top_k: int = 5,
        filter_doc_ids: list[int | str] | None = None,
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
