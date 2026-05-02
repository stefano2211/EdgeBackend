"""Vector persistence layer (Qdrant)."""

from src.persistencia.vector.qdrant_client import get_qdrant_client, collection_name, ensure_collection
from src.persistencia.vector.vector_repository import VectorRepository

__all__ = [
    "get_qdrant_client",
    "collection_name",
    "ensure_collection",
    "VectorRepository",
]
