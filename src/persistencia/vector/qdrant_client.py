"""Async Qdrant client singleton and collection management.

Layer: persistencia/vector (data access layer)
All Qdrant connectivity and collection-level operations live here.
"""

from __future__ import annotations

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    HnswConfigDiff,
    KeywordIndexParams,
    TextIndexParams,
)

from src.core.config import settings
from src.core.logging import logging

logger = logging.getLogger(__name__)

_qdrant_client: AsyncQdrantClient | None = None


def get_qdrant_client() -> AsyncQdrantClient:
    """Return singleton AsyncQdrantClient (gRPC preferred for speed)."""
    global _qdrant_client
    if _qdrant_client is None:
        # Prefer gRPC for 2-3x throughput on batch upserts/search.
        # REST is used as fallback if gRPC port is unavailable.
        _qdrant_client = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
            prefer_grpc=True,
        )
        logger.info("Qdrant client initialised: %s", settings.QDRANT_URL)
    return _qdrant_client


def collection_name(knowledge_base_id: int | str) -> str:
    return f"kb_{knowledge_base_id}"


async def ensure_collection(
    knowledge_base_id: int | str,
    dimension: int = 384,
    vectors_on_disk: bool = False,
) -> str:
    """Create Qdrant collection with HNSW tuning + payload indexes.

    2026 Qdrant best practices applied:
    - HNSW tuned for recall/speed (m=16, ef_construct=100)
    - Payload indexes on doc_id and filename for fast filtering/deletion
    - on_disk vectors for cold data (optional, default off for edge workloads)
    """
    client = get_qdrant_client()
    name = collection_name(knowledge_base_id)

    exists = await client.collection_exists(name)
    if exists:
        return name

    await client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(
            size=dimension,
            distance=Distance.COSINE,
            on_disk=vectors_on_disk,
        ),
        hnsw_config=HnswConfigDiff(
            m=16,
            ef_construct=100,
        ),
    )

    # Payload indexes: critical for fast filtered delete_by_doc_id and search
    await client.create_payload_index(
        collection_name=name,
        field_name="doc_id",
        field_schema=KeywordIndexParams(),
        wait=True,
    )
    await client.create_payload_index(
        collection_name=name,
        field_name="filename",
        field_schema=TextIndexParams(),
        wait=True,
    )

    logger.info(
        "Created Qdrant collection: %s (dim=%d, on_disk=%s, payload_indexes=2)",
        name,
        dimension,
        vectors_on_disk,
    )
    return name
