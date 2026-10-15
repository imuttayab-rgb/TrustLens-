"""Exercise the upload/backfill paths against a KMS-less S3-compatible adapter."""
from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError
from PIL import Image

from trustlens.core.domain.entities import StoredFile
from trustlens.core.domain.enums import FilePurpose
from trustlens.shared.storage import S3ObjectStorage
from trustlens_api.modules.photos import backfill as photo_backfill
from trustlens_api.api.v1.routers.listings import ListingImageRequest, add_listing_image


class KmslessS3:
    def __init__(self, fail_thumbnail=False):
        out = BytesIO()
        Image.new("RGB", (80, 60), (20, 70, 120)).save(out, "PNG")
        self.raw = out.getvalue()
        self.writes = []
        self.fail_thumbnail = fail_thumbnail

    def get_object(self, **kwargs):
        return {"Body": BytesIO(self.raw)}

    def put_object(self, **kwargs):
        self.writes.append(kwargs)
        if "ServerSideEncryption" in kwargs:
            raise ClientError({"Error": {"Code": "NotImplemented", "Message": "KMS not configured"}}, "PutObject")
        if self.fail_thumbnail and kwargs["Key"].endswith("_thumb.jpg"):
            raise ClientError({"Error": {"Code": "AccessDenied", "Message": "test failure"}}, "PutObject")
        return {}


def fixture(fail_thumbnail=False):
    client = KmslessS3(fail_thumbnail)
    storage = object.__new__(S3ObjectStorage)
    storage._client = client
    now = datetime.now(timezone.utc)
    uid, lid, fid = uuid4(), uuid4(), uuid4()
    stored = StoredFile(id=fid, owner_user_id=uid, purpose=FilePurpose.LISTING_IMAGE,
                        bucket="test-listings", object_key="original-upload", mime_type="image/png",
                        size_bytes=len(client.raw), sha256=b"", created_at=now)
    uow = AsyncMock()
    uow.__aenter__.return_value = uow
    uow.files.get.return_value = stored
    uow.listings.count_images.return_value = 0
    index = AsyncMock()
    index.exact_match.return_value = False
    index.candidates.return_value = []
    index.missing_count.return_value = 0
    container = SimpleNamespace(storage=storage, clock=SimpleNamespace(now=lambda: now), ids=SimpleNamespace(new=uuid4))
    return client, storage, stored, uow, index, container, lid


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_thumbnail", [False, True])
async def test_normal_attachment_works_without_kms_and_never_commits_partial_write(fail_thumbnail):
    client, storage, stored, uow, index, container, lid = fixture(fail_thumbnail)
    with patch("trustlens_api.api.v1.routers.listings.GetListing.execute", AsyncMock(return_value=SimpleNamespace(id=lid))), patch("trustlens.db.photo_guard.PhotoIndex", return_value=index):
        call = add_listing_image(lid, ListingImageRequest(file_id=stored.id),
                                 SimpleNamespace(id=uuid4(), user_id=stored.owner_user_id),
                                 container, uow, SimpleNamespace(request_id="test"))
        if fail_thumbnail:
            with pytest.raises(ClientError):
                await call
        else:
            await call
    assert len(client.writes) == 2
    assert all("ServerSideEncryption" not in x for x in client.writes)
    assert all(x["Bucket"] == "test-listings" and x["Key"] != stored.object_key for x in client.writes)
    assert uow.commit.await_count == (0 if fail_thumbnail else 1)
    assert index.add.await_count == (0 if fail_thumbnail else 1)
    assert uow.listings.create_image.await_count == (0 if fail_thumbnail else 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_thumbnail", [False, True])
async def test_legacy_backfill_works_without_kms_and_keeps_progress_transactional(fail_thumbnail):
    client, storage, stored, uow, index, _, lid = fixture(fail_thumbnail)
    image = SimpleNamespace(id=uuid4(), file_id=stored.id)
    # Row lookup, two SQL updates, next lookup, ready-state update.
    uow.session.execute.side_effect = [SimpleNamespace(first=lambda: (image, stored.owner_user_id)), None, None, SimpleNamespace(first=lambda: None), None]
    engine = SimpleNamespace(dispose=AsyncMock())
    with patch.object(photo_backfill, "get_settings", return_value=SimpleNamespace(database=None, storage=None)), patch.object(photo_backfill, "create_engine", return_value=engine), patch.object(photo_backfill, "create_session_factory"), patch.object(photo_backfill, "build_storage", return_value=storage), patch.object(photo_backfill, "SqlAlchemyUnitOfWork", return_value=uow), patch.object(photo_backfill, "PhotoIndex", return_value=index):
        if fail_thumbnail:
            with pytest.raises(ClientError):
                await photo_backfill.run()
        else:
            await photo_backfill.run()
    assert len(client.writes) == 2
    assert all("ServerSideEncryption" not in x for x in client.writes)
    assert all(x["Key"].startswith("listing_checked_legacy/") for x in client.writes)
    assert index.add.await_count == (0 if fail_thumbnail else 1)
    assert uow.commit.await_count == (0 if fail_thumbnail else 2)
    assert uow.session.execute.await_count == (1 if fail_thumbnail else 5)
    engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_default_storage_encryption_is_not_weakened_or_silently_retried():
    client, storage, *_ = fixture()
    with pytest.raises(ClientError):
        await storage.put(bucket="test-documents", object_key="private-document", data=b"test", content_type="image/jpeg")
    assert len(client.writes) == 1
    assert client.writes[0]["ServerSideEncryption"] == "AES256"


@pytest.mark.asyncio
async def test_completed_backfill_does_not_rewrite_photos_on_resume():
    client, storage, _, uow, index, *_ = fixture()
    uow.session.execute.side_effect = [SimpleNamespace(first=lambda: None), None]
    engine = SimpleNamespace(dispose=AsyncMock())
    with patch.object(photo_backfill, "get_settings", return_value=SimpleNamespace(database=None, storage=None)), patch.object(photo_backfill, "create_engine", return_value=engine), patch.object(photo_backfill, "create_session_factory"), patch.object(photo_backfill, "build_storage", return_value=storage), patch.object(photo_backfill, "SqlAlchemyUnitOfWork", return_value=uow), patch.object(photo_backfill, "PhotoIndex", return_value=index):
        await photo_backfill.run()
    assert not client.writes
    index.add.assert_not_awaited()
    uow.commit.assert_awaited_once()
