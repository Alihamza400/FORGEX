from __future__ import annotations

from datetime import timedelta
from io import BytesIO
from typing import Any

from forge.core.config import settings
from forge.core.logging import get_logger
from minio import Minio as SyncMinio
from minio.error import S3Error

logger = get_logger("forge.storage.minio")


class MinIOError(Exception):
    pass


class MinIOStorage:
    def __init__(
        self,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        secure: bool | None = None,
        default_bucket: str | None = None,
    ) -> None:
        self.endpoint = endpoint or settings.minio_endpoint
        self.access_key = access_key or settings.minio_access_key
        self.secret_key = secret_key or settings.minio_secret_key
        self.secure = secure if secure is not None else settings.minio_secure
        self.default_bucket = default_bucket or settings.minio_default_bucket
        self._client: SyncMinio | None = None

    def connect(self) -> None:
        logger.info("connecting to minio", endpoint=self.endpoint)
        try:
            self._client = SyncMinio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )
            self._ensure_bucket(self.default_bucket)
            logger.info("minio connected", bucket=self.default_bucket)
        except Exception as e:
            raise MinIOError(f"Failed to connect to MinIO: {e}") from e

    def close(self) -> None:
        self._client = None
        logger.info("minio client closed")

    @property
    def client(self) -> SyncMinio:
        if self._client is None:
            self.connect()
        return self._client  # type: ignore[return-value]

    def _ensure_bucket(self, bucket: str) -> None:
        try:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)
                logger.info("created minio bucket", bucket=bucket)
        except S3Error as e:
            raise MinIOError(f"Failed to ensure bucket '{bucket}': {e}") from e

    async def upload_bytes(
        self,
        data: bytes,
        key: str,
        bucket: str | None = None,
        content_type: str = "application/octet-stream",
    ) -> str:
        bucket = bucket or self.default_bucket
        try:
            self._ensure_bucket(bucket)
            self.client.put_object(
                bucket,
                key,
                data=BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
            logger.debug("uploaded to minio", bucket=bucket, key=key, size=len(data))
            return f"{bucket}/{key}"
        except S3Error as e:
            raise MinIOError(f"Failed to upload to MinIO: {e}") from e

    async def upload_file(
        self,
        file_path: str,
        key: str,
        bucket: str | None = None,
    ) -> str:
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            raise MinIOError(f"File not found: {file_path}")

        bucket = bucket or self.default_bucket
        try:
            self._ensure_bucket(bucket)
            with open(file_path, "rb") as f:
                self.client.put_object(
                    bucket,
                    key,
                    data=f,
                    length=path.stat().st_size,
                )
            logger.debug("uploaded file to minio", bucket=bucket, key=key)
            return f"{bucket}/{key}"
        except S3Error as e:
            raise MinIOError(f"Failed to upload file to MinIO: {e}") from e

    async def download_bytes(self, key: str, bucket: str | None = None) -> bytes:
        bucket = bucket or self.default_bucket
        try:
            response = self.client.get_object(bucket, key)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except S3Error as e:
            raise MinIOError(f"Failed to download from MinIO: {e}") from e

    async def download_file(
        self,
        key: str,
        dest_path: str,
        bucket: str | None = None,
    ) -> str:
        bucket = bucket or self.default_bucket
        from pathlib import Path

        dest = Path(dest_path)
        try:
            self.client.fget_object(bucket, key, str(dest))
            logger.debug("downloaded file from minio", bucket=bucket, key=key, dest=str(dest))
            return str(dest)
        except S3Error as e:
            raise MinIOError(f"Failed to download file from MinIO: {e}") from e

    async def list_files(
        self,
        prefix: str = "",
        bucket: str | None = None,
        recursive: bool = True,
    ) -> list[dict[str, Any]]:
        bucket = bucket or self.default_bucket
        try:
            objects = self.client.list_objects(
                bucket,
                prefix=prefix,
                recursive=recursive,
            )
            results = []
            for obj in objects:
                results.append({
                    "key": obj.object_name,
                    "size": obj.size,
                    "etag": obj.etag,
                    "last_modified": obj.last_modified.isoformat() if obj.last_modified else "",
                })
            return results
        except S3Error as e:
            raise MinIOError(f"Failed to list files in MinIO: {e}") from e

    async def delete_file(self, key: str, bucket: str | None = None) -> bool:
        bucket = bucket or self.default_bucket
        try:
            self.client.remove_object(bucket, key)
            logger.debug("deleted from minio", bucket=bucket, key=key)
            return True
        except S3Error as e:
            raise MinIOError(f"Failed to delete from MinIO: {e}") from e

    async def presigned_url(
        self,
        key: str,
        bucket: str | None = None,
        expires_seconds: int = 3600,
    ) -> str:
        bucket = bucket or self.default_bucket
        try:
            url = self.client.presigned_get_object(
                bucket,
                key,
                expires=timedelta(seconds=expires_seconds),
            )
            return url
        except S3Error as e:
            raise MinIOError(f"Failed to generate presigned URL: {e}") from e

    async def health(self) -> dict[str, Any]:
        try:
            buckets = self.client.list_buckets()
            return {
                "status": "ok",
                "buckets": [b.name for b in buckets],
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
