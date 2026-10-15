"""Local MinIO split-origin presign regression tests (no network or real IDs)."""

from __future__ import annotations

import asyncio
from urllib.parse import urlsplit

from trustlens.shared.config.settings import StorageSettings
from trustlens.shared.storage import S3ObjectStorage


def test_browser_presigns_use_public_host_but_internal_client_keeps_private_host() -> None:
    storage = S3ObjectStorage(
        StorageSettings(
            storage_endpoint_url="http://minio:9000",
            storage_public_endpoint_url="http://localhost:9000",
            storage_access_key_id="demo-test-key",
            storage_secret_access_key="demo-test-secret",
        )
    )
    signed = asyncio.run(
        storage.presign_upload(
            bucket="trustlens-documents",
            object_key="synthetic/front.jpg",
            content_type="image/jpeg",
            max_bytes=1024,
            ttl_seconds=300,
        )
    )
    download = asyncio.run(
        storage.presign_download(
            bucket="trustlens-documents", object_key="synthetic/front.jpg", ttl_seconds=300
        )
    )
    assert urlsplit(signed.url).netloc == "localhost:9000"
    assert urlsplit(download).netloc == "localhost:9000"
    assert "x-amz-signature" in signed.fields
    assert "X-Amz-Signature=" in download
    assert storage._client.meta.endpoint_url == "http://minio:9000"
    assert storage._presign_client.meta.endpoint_url == "http://localhost:9000"


def test_old_single_endpoint_config_keeps_original_behavior() -> None:
    storage = S3ObjectStorage(
        StorageSettings(
            storage_endpoint_url="http://minio:9000",
            storage_access_key_id="demo-test-key",
            storage_secret_access_key="demo-test-secret",
        )
    )
    assert storage._client is storage._presign_client
    signed = asyncio.run(
        storage.presign_download(
            bucket="trustlens-listings", object_key="synthetic/test.jpg", ttl_seconds=60
        )
    )
    assert urlsplit(signed).netloc == "minio:9000"
