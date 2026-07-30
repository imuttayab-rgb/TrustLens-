"""Object storage adapters.

Uploads are **presigned**: image bytes go straight from the browser to the
bucket and never traverse the API process. That removes a memory-exhaustion
vector and a large chunk of latency, and is part of why the API container can
stay small (ADR-0003).

Buckets holding identity documents are private, with no public ACL and no CDN.
Reads happen only through short-lived presigned GETs, authorised per request.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from trustlens.core.domain.ports import ObjectStorage, PresignedUpload
from trustlens.shared.config.settings import StorageSettings


def sniff_mime(data: bytes) -> str | None:
    """Detect the real content type from leading bytes.

    The client's Content-Type header and the file extension are BOTH ignored:
    a .jpg that is actually HTML is a stored-XSS vector, and a polyglot file
    is how image parsers get exploited.
    """
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


class S3ObjectStorage(ObjectStorage):
    """S3-compatible storage (AWS S3, Cloudflare R2, MinIO).

    boto3 is synchronous, so every call is dispatched to a thread. Calling it
    directly from an async handler would block the event loop for the whole
    round trip and silently serialise the API.
    """

    def __init__(self, settings: StorageSettings) -> None:
        self._settings = settings
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.storage_endpoint_url,
            region_name=settings.storage_region,
            aws_access_key_id=(
                settings.storage_access_key_id.get_secret_value()
                if settings.storage_access_key_id
                else None
            ),
            aws_secret_access_key=(
                settings.storage_secret_access_key.get_secret_value()
                if settings.storage_secret_access_key
                else None
            ),
            config=BotoConfig(signature_version="s3v4", retries={"max_attempts": 3}),
        )

    async def presign_upload(
        self,
        *,
        bucket: str,
        object_key: str,
        content_type: str,
        max_bytes: int,
        ttl_seconds: int,
    ) -> PresignedUpload:
        def _presign() -> dict[str, Any]:
            return self._client.generate_presigned_post(
                Bucket=bucket,
                Key=object_key,
                Fields={"Content-Type": content_type},
                Conditions=[
                    {"Content-Type": content_type},
                    # Enforced by the storage service itself, so an oversized
                    # upload is rejected before it costs us bandwidth.
                    ["content-length-range", 1, max_bytes],
                ],
                ExpiresIn=ttl_seconds,
            )

        result = await asyncio.to_thread(_presign)
        return PresignedUpload(
            url=result["url"],
            fields=result["fields"],
            object_key=object_key,
            expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
        )

    async def presign_download(self, *, bucket: str, object_key: str, ttl_seconds: int) -> str:
        def _presign() -> str:
            return str(
                self._client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": bucket, "Key": object_key},
                    ExpiresIn=ttl_seconds,
                )
            )

        return await asyncio.to_thread(_presign)

    async def get(self, *, bucket: str, object_key: str) -> bytes:
        def _get() -> bytes:
            response = self._client.get_object(Bucket=bucket, Key=object_key)
            return bytes(response["Body"].read())

        return await asyncio.to_thread(_get)

    async def put(self, *, bucket: str, object_key: str, data: bytes, content_type: str) -> None:
        def _put() -> None:
            self._client.put_object(
                Bucket=bucket,
                Key=object_key,
                Body=data,
                ContentType=content_type,
                # Server-side encryption, on top of the app-level envelope
                # encryption applied to extracted CNIC fields.
                ServerSideEncryption="AES256",
            )

        await asyncio.to_thread(_put)

    async def delete(self, *, bucket: str, object_key: str) -> None:
        await asyncio.to_thread(lambda: self._client.delete_object(Bucket=bucket, Key=object_key))

    async def exists(self, *, bucket: str, object_key: str) -> bool:
        return await self.head(bucket=bucket, object_key=object_key) is not None

    async def head(self, *, bucket: str, object_key: str) -> dict[str, Any] | None:
        def _head() -> dict[str, Any] | None:
            try:
                response = self._client.head_object(Bucket=bucket, Key=object_key)
            except ClientError as exc:
                if exc.response["Error"]["Code"] in {"404", "NoSuchKey", "NotFound"}:
                    return None
                raise
            return {
                "size_bytes": int(response["ContentLength"]),
                "content_type": response.get("ContentType"),
                "etag": str(response.get("ETag", "")).strip('"'),
            }

        return await asyncio.to_thread(_head)


class LocalObjectStorage(ObjectStorage):
    """Filesystem-backed storage for tests and offline development.

    Presigned URLs are simulated with an API route; the API still validates
    ownership before streaming a file, so the security model is unchanged.
    """

    def __init__(self, root: Path, *, base_url: str = "http://localhost:8000") -> None:
        self._root = root
        self._base_url = base_url.rstrip("/")
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, bucket: str, object_key: str) -> Path:
        resolved = (self._root / bucket / object_key).resolve()
        # Containment check: an object key must never escape its bucket via
        # `../`. Keys are server-generated, but defence in depth is cheap.
        if not str(resolved).startswith(str((self._root / bucket).resolve())):
            raise ValueError("invalid object key")
        return resolved

    async def presign_upload(
        self, *, bucket: str, object_key: str, content_type: str, max_bytes: int, ttl_seconds: int
    ) -> PresignedUpload:
        return PresignedUpload(
            url=f"{self._base_url}/api/v1/files/local-upload",
            fields={"bucket": bucket, "key": object_key, "Content-Type": content_type},
            object_key=object_key,
            expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
        )

    async def presign_download(self, *, bucket: str, object_key: str, ttl_seconds: int) -> str:
        return f"{self._base_url}/api/v1/files/local/{bucket}/{object_key}"

    async def get(self, *, bucket: str, object_key: str) -> bytes:
        return self._path(bucket, object_key).read_bytes()

    async def put(self, *, bucket: str, object_key: str, data: bytes, content_type: str) -> None:
        path = self._path(bucket, object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    async def delete(self, *, bucket: str, object_key: str) -> None:
        self._path(bucket, object_key).unlink(missing_ok=True)

    async def exists(self, *, bucket: str, object_key: str) -> bool:
        return self._path(bucket, object_key).exists()

    async def head(self, *, bucket: str, object_key: str) -> dict[str, Any] | None:
        path = self._path(bucket, object_key)
        if not path.exists():
            return None
        data = path.read_bytes()
        return {"size_bytes": len(data), "content_type": sniff_mime(data[:16]), "etag": ""}


def build_storage(settings: StorageSettings, *, local_root: Path | None = None) -> ObjectStorage:
    if settings.storage_provider == "local":
        return LocalObjectStorage(local_root or Path(".docker-data/storage"))
    return S3ObjectStorage(settings)


__all__ = ["LocalObjectStorage", "S3ObjectStorage", "build_storage", "sniff_mime"]
