"""StoragePort — protocol for S3-compatible object storage.

Abstraction over MinIO / AWS S3 / any S3-compatible backend.
KnowledgeBase-scoped keys use prefix: kb/{knowledge_base_id}/{object_key}
"""

from __future__ import annotations

from typing import Protocol


class StoragePort(Protocol):
    """Async object storage operations."""

    async def upload(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload bytes to the storage backend and return the key."""
        ...

    async def download(self, key: str) -> bytes:
        """Download object bytes by key."""
        ...

    async def delete(self, key: str) -> None:
        """Delete a single object by key."""
        ...

    async def exists(self, key: str) -> bool:
        """Check whether an object exists."""
        ...

    async def delete_prefix(self, prefix: str) -> int:
        """Delete all objects whose keys start with *prefix*.

        Returns:
            Number of objects deleted.
        """
        ...
