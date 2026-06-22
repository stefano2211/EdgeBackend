"""Vector persistence layer (Qdrant)."""

from backend.infrastructure.vector.qdrant_client import get_qdrant_client, collection_name, ensure_collection
from backend.infrastructure.vector.vector_repository import VectorRepository

__all__ = [
    "get_qdrant_client",
    "collection_name",
    "ensure_collection",
    "VectorRepository",
]
