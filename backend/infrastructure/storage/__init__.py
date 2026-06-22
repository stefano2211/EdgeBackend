"""Object storage — MinIO."""

from backend.domain.ports.storage import StoragePort
from backend.infrastructure.storage.minio import MinioStorageRepository

__all__ = ["StoragePort", "MinioStorageRepository"]
