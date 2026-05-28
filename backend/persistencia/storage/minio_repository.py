"""MinIO S3-compatible object storage repository.

Wraps the synchronous minio SDK in asyncio.to_thread so the event loop
never blocks on I/O.

Key convention:
    kb/{knowledge_base_id}/{uuid}.{ext}

All keys live in a single bucket (MINIO_BUCKET) with prefix isolation.
"""

from __future__ import annotations

import asyncio

from minio import Minio
from minio.error import S3Error

from backend.core.config import settings
from backend.core.logging import logging

logger = logging.getLogger(__name__)


class MinioStorageRepository:
    """Async MinIO repository wrapping the sync minio SDK."""

    def __init__(
        self,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket: str | None = None,
        secure: bool | None = None,
        region: str | None = None,
    ) -> None:
        self._endpoint = endpoint or settings.MINIO_ENDPOINT
        self._access_key = access_key or settings.MINIO_ACCESS_KEY
        self._secret_key = secret_key or settings.MINIO_SECRET_KEY
        self._bucket = bucket or settings.MINIO_BUCKET
        self._secure = secure if secure is not None else settings.MINIO_SECURE
        self._region = region or settings.MINIO_REGION

        self._client: Minio | None = None

    @property
    def client(self) -> Minio:
        """Lazy-init the Minio client."""
        if self._client is None:
            self._client = Minio(
                self._endpoint,
                access_key=self._access_key,
                secret_key=self._secret_key,
                secure=self._secure,
                region=self._region,
            )
        return self._client

    async def _ensure_bucket(self) -> None:
        """Create bucket if it does not already exist (idempotent)."""
        loop = asyncio.get_running_loop()

        def _check_and_create() -> None:
            found = self.client.bucket_exists(self._bucket)
            if not found:
                try:
                    self.client.make_bucket(self._bucket)
                    logger.info("Created MinIO bucket: %s", self._bucket)
                except S3Error as e:
                    if e.code == "BucketAlreadyOwnedByYou":
                        pass  # Race-condition safe
                    else:
                        raise
            else:
                logger.debug("MinIO bucket already exists: %s", self._bucket)

        await loop.run_in_executor(None, _check_and_create)

    async def upload(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload bytes and return the S3 key."""
        await self._ensure_bucket()
        loop = asyncio.get_running_loop()
        from io import BytesIO

        def _put() -> str:
            self.client.put_object(
                self._bucket,
                key,
                data=BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
            return key

        result = await loop.run_in_executor(None, _put)
        logger.debug("Uploaded to MinIO: %s/%s", self._bucket, key)
        return result

    async def download(self, key: str) -> bytes:
        """Download object bytes."""
        loop = asyncio.get_running_loop()

        def _get() -> bytes:
            try:
                resp = self.client.get_object(self._bucket, key)
                return resp.read()
            except S3Error as e:
                if e.code == "NoSuchKey":
                    raise FileNotFoundError(f"Object not found: {key}") from e
                raise

        return await loop.run_in_executor(None, _get)

    async def delete(self, key: str) -> None:
        """Delete a single object."""
        loop = asyncio.get_running_loop()

        def _remove() -> None:
            try:
                self.client.remove_object(self._bucket, key)
            except S3Error as e:
                if e.code == "NoSuchKey":
                    return  # Idempotent
                raise

        await loop.run_in_executor(None, _remove)
        logger.debug("Deleted from MinIO: %s/%s", self._bucket, key)

    async def exists(self, key: str) -> bool:
        """Check whether an object exists."""
        loop = asyncio.get_running_loop()

        def _stat() -> bool:
            try:
                self.client.stat_object(self._bucket, key)
                return True
            except S3Error as e:
                if e.code == "NoSuchKey":
                    return False
                raise

        return await loop.run_in_executor(None, _stat)

    async def delete_prefix(self, prefix: str) -> int:
        """Delete all objects whose keys start with *prefix*.

        Returns:
            Number of objects removed.
        """
        loop = asyncio.get_running_loop()

        def _remove_all() -> int:
            objects = self.client.list_objects(self._bucket, prefix=prefix, recursive=True)
            keys = [obj.object_name for obj in objects if obj.object_name]
            if keys:
                errors = self.client.remove_objects(self._bucket, keys)
                for err in errors:
                    logger.warning("MinIO delete error for %s: %s", err.name, err.cause)
            return len(keys)

        count = await loop.run_in_executor(None, _remove_all)
        logger.info("Deleted %d objects with prefix '%s' from MinIO", count, prefix)
        return count
