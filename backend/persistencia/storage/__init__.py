"""Storage layer — S3-compatible object storage abstraction.

Follows the same pattern as persistencia/vector/:
- StoragePort: protocol
- MinioStorageRepository: concrete MinIO implementation
"""

from backend.persistencia.storage.storage_port import StoragePort
from backend.persistencia.storage.minio_repository import MinioStorageRepository

__all__ = ["StoragePort", "MinioStorageRepository"]
