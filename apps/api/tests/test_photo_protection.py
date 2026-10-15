"""Photo transformations, false positives and fail-closed upload boundaries."""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from PIL import Image, ImageDraw, ImageOps
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from trustlens.core.domain.errors import ConflictError, RateLimitExceeded, ValidationError
from trustlens.db import models as m
from trustlens.db.photo_guard import PhotoIndex, photos_cleared
from trustlens_api.api.v1.routers.listings import ListingImageRequest, add_listing_image
from trustlens_api.modules.photos.guard import prepare_photo, visually_matches


def product(seed=1):
    import random

    rng = random.Random(seed)
    img = Image.new("RGB", (640, 480), (125 + seed % 30, 125, 100))
    draw = ImageDraw.Draw(img)
    for _ in range(170):
        x, y = rng.randrange(640), rng.randrange(480)
        draw.rectangle(
            (x, y, x + rng.randrange(4, 55), y + rng.randrange(4, 55)),
            fill=tuple(rng.randrange(256) for _ in range(3)),
        )
    # Same phone silhouette, differing photographed contents and backgrounds.
    draw.rounded_rectangle((240, 70, 415, 420), radius=20, fill=(20, 22, 30))
    draw.rectangle((252, 94, 400, 390), fill=(40, 65 + seed % 120, 130))
    draw.ellipse((315, 77, 330, 91), fill="gray")
    return img


def encode(img, fmt="PNG", **kwargs):
    out = BytesIO()
    img.save(out, format=fmt, **kwargs)
    return out.getvalue()


@pytest.mark.parametrize(
    "change",
    [
        lambda im: im,
        lambda im: im.resize((320, 240)),
        lambda im: ImageOps.mirror(im),
        lambda im: im.crop((51, 38, 589, 442)),
        lambda im: ImageOps.expand(im, border=55, fill="white"),
    ],
)
def test_reused_photos_detected(change):
    original = prepare_photo(encode(product()))
    altered = prepare_photo(encode(change(product()), "JPEG", quality=76))
    assert set(original.bands) & set(altered.bands), "indexed shortlist must include the copy"
    assert visually_matches(original.fingerprint, altered.fingerprint)


def test_exact_and_served_file_digests_are_indexed():
    original = prepare_photo(encode(product()))
    downloaded = prepare_photo(original.jpeg)
    assert set(original.digests) & set(downloaded.digests)


def test_different_accounts_different_photos_same_product_are_not_equal():
    original = prepare_photo(encode(product()))
    for seed in range(2, 22):
        other = prepare_photo(encode(product(seed)))
        assert not visually_matches(original.fingerprint, other.fingerprint)


def test_blank_backgrounds_are_not_visual_evidence():
    first = prepare_photo(encode(Image.new("RGB", (300, 200), "white")))
    second = prepare_photo(encode(Image.new("RGB", (300, 200), (248, 248, 248))))
    assert not visually_matches(first.fingerprint, second.fingerprint)


@pytest.mark.parametrize("raw", [b"invalid", b"", b"x" * (10 * 1024 * 1024 + 1)])
def test_invalid_or_oversized_input_cannot_pass(raw):
    with pytest.raises((ValueError, OSError)):
        prepare_photo(raw)


def test_orientation_metadata_stripped():
    img = product()
    exif = Image.Exif()
    exif[274] = 6
    result = prepare_photo(encode(img, "JPEG", exif=exif))
    assert (result.width, result.height) == (480, 640)
    assert not Image.open(BytesIO(result.jpeg)).getexif()


@pytest.mark.asyncio
async def test_busy_and_unready_checks_fail_closed():
    session = AsyncMock()
    session.execute.return_value = SimpleNamespace(scalar_one=lambda: False)
    with pytest.raises(RateLimitExceeded):
        await PhotoIndex(session).lock()
    session.get.return_value = None
    with pytest.raises(RateLimitExceeded):
        await PhotoIndex(session).require_ready()


@pytest.mark.asyncio
async def test_candidate_overflow_does_not_silently_pass():
    session = AsyncMock()
    session.execute.return_value = SimpleNamespace(scalars=lambda: [{}] * 129)
    with pytest.raises(RateLimitExceeded):
        await PhotoIndex(session).candidates(uuid4(), ["0:abcd"])


def test_publication_predicate_is_correlated_and_uses_missing_fingerprints():
    query = select(m.ListingModel.id).where(photos_cleared())
    sql = str(query.compile(dialect=postgresql.dialect()))
    assert "NOT (EXISTS" in sql
    assert "LEFT OUTER JOIN photo_fingerprints" in sql
    assert "listing_images.listing_id = listings.id" in sql
    assert "photo_fingerprints.image_id IS NULL" in sql
    assert ", listings" not in sql.split("EXISTS", 1)[1]


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["exact", "visual", "busy", "invalid", "storage"])
async def test_rejected_or_failed_photo_never_attached(reason):
    uid, lid, fid = uuid4(), uuid4(), uuid4()
    seller = SimpleNamespace(id=uuid4(), user_id=uid)
    stored = SimpleNamespace(
        id=fid,
        owner_user_id=uid,
        purpose=SimpleNamespace(value="LISTING_IMAGE"),
        bucket="test",
        object_key="upload",
    )
    uow = SimpleNamespace(
        session=AsyncMock(), files=AsyncMock(), listings=AsyncMock(), commit=AsyncMock()
    )
    uow.files.get.return_value = stored
    uow.listings.count_images.return_value = 0
    container = SimpleNamespace(storage=AsyncMock())
    container.storage.get.return_value = b"invalid" if reason == "invalid" else encode(product())
    if reason == "storage":
        container.storage.get.side_effect = RuntimeError("storage offline")
    index = AsyncMock()
    index.exact_match.return_value = reason == "exact"
    index.candidates.return_value = (
        [prepare_photo(encode(product())).fingerprint] if reason == "visual" else []
    )
    if reason == "busy":
        index.lock.side_effect = RateLimitExceeded()
    get_listing = AsyncMock(return_value=SimpleNamespace(id=lid))
    with (
        patch("trustlens_api.api.v1.routers.listings.GetListing.execute", get_listing),
        patch("trustlens.db.photo_guard.PhotoIndex", return_value=index),
    ):
        with pytest.raises((ConflictError, RateLimitExceeded, ValidationError, RuntimeError)):
            await add_listing_image(
                lid,
                ListingImageRequest(file_id=fid),
                seller,
                container,
                uow,
                SimpleNamespace(request_id="test"),
            )
    uow.listings.create_image.assert_not_called()
    index.add.assert_not_called()
    uow.commit.assert_not_called()
    container.storage.put.assert_not_called()


@pytest.mark.asyncio
async def test_success_uses_immutable_key_and_indexes_before_commit():
    from datetime import datetime, timezone

    from trustlens.core.domain.entities import StoredFile
    from trustlens.core.domain.enums import FilePurpose

    uid, lid, fid = uuid4(), uuid4(), uuid4()
    now = datetime.now(timezone.utc)
    seller = SimpleNamespace(id=uuid4(), user_id=uid)
    stored = StoredFile(
        id=fid,
        owner_user_id=uid,
        purpose=FilePurpose.LISTING_IMAGE,
        bucket="test",
        object_key="mutable-upload",
        mime_type="image/png",
        size_bytes=100,
        sha256=b"",
        created_at=now,
    )
    uow = SimpleNamespace(
        session=AsyncMock(), files=AsyncMock(), listings=AsyncMock(), commit=AsyncMock()
    )
    uow.files.get.return_value = stored
    uow.listings.count_images.return_value = 0
    container = SimpleNamespace(
        storage=AsyncMock(), clock=SimpleNamespace(now=lambda: now), ids=SimpleNamespace(new=uuid4)
    )
    container.storage.get.return_value = encode(product())
    index = AsyncMock()
    index.exact_match.return_value = False
    index.candidates.return_value = []
    order = []
    index.add.side_effect = lambda *args: order.append("indexed")
    uow.commit.side_effect = lambda: order.append("committed")
    with (
        patch(
            "trustlens_api.api.v1.routers.listings.GetListing.execute",
            AsyncMock(return_value=SimpleNamespace(id=lid)),
        ),
        patch("trustlens.db.photo_guard.PhotoIndex", return_value=index),
    ):
        await add_listing_image(
            lid,
            ListingImageRequest(file_id=fid),
            seller,
            container,
            uow,
            SimpleNamespace(request_id="test"),
        )
    assert order == ["indexed", "committed"]
    frozen = uow.files.add.call_args.args[0]
    assert frozen.id != stored.id and frozen.object_key.startswith("listing_checked/")
    assert all(
        call.kwargs["object_key"] != stored.object_key
        for call in container.storage.put.call_args_list
    )
    assert index.exact_match.call_args.args[0] == uid
    assert index.candidates.call_args.args[0] == uid
    assert uow.listings.create_image.call_args.args[0].file_id == frozen.id


def test_local_pixel_limit_is_checked_before_full_decode():
    with pytest.raises(ValueError, match="20 megapixels"):
        prepare_photo(encode(Image.new("RGB", (6000, 4000), "gray"), "JPEG"))
