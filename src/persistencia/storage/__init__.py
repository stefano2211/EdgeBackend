"""Storage layer — S3-compatible object storage abstraction.

Follows the same pattern as persistencia/vector/:
- StoragePort: protocol
- MinioStorageRepository: concrete MinIO implementation
"""

from src.persistencia.storage.storage_port import StoragePort
from src.persistencia.storage.minio_repository import MinioStorageRepository

__all__ = ["StoragePort", "MinioStorageRepository"]
