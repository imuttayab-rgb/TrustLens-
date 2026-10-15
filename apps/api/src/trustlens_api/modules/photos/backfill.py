"""Resumable, one-photo-at-a-time index of pre-existing listing images.

Run only during the installer's short API/worker maintenance window. Existing
duplicates are grandfathered, not deleted or scored. Future attachments always
use the normal check; no client parameter can grant a legacy exemption.
"""

from __future__ import annotations

import asyncio
import hashlib

from anyio import to_thread
from sqlalchemy import select, update

from trustlens.db import models as m
from trustlens.db.photo_guard import PhotoIndex
from trustlens.db.session import create_engine, create_session_factory
from trustlens.db.unit_of_work import SqlAlchemyUnitOfWork
from trustlens.shared.config import get_settings
from trustlens.shared.storage import build_storage
from trustlens_api.modules.photos.guard import prepare_photo


async def run() -> None:
    settings = get_settings()
    engine = create_engine(settings.database)
    factory = create_session_factory(engine)
    storage = build_storage(settings.storage)
    completed = 0
    try:
        while True:
            async with SqlAlchemyUnitOfWork(factory) as uow:
                index = PhotoIndex(uow.session)
                await index.lock()
                row = (
                    await uow.session.execute(
                        select(m.ListingImageModel, m.SellerProfile.user_id)
                        .join(m.ListingModel, m.ListingModel.id == m.ListingImageModel.listing_id)
                        .join(m.SellerProfile, m.SellerProfile.id == m.ListingModel.seller_id)
                        .outerjoin(
                            m.PhotoFingerprintModel,
                            m.PhotoFingerprintModel.image_id == m.ListingImageModel.id,
                        )
                        .where(m.PhotoFingerprintModel.image_id.is_(None))
                        .order_by(m.ListingImageModel.created_at, m.ListingImageModel.id)
                        .limit(1)
                    )
                ).first()
                if row is None:
                    if await index.missing_count():
                        raise RuntimeError(
                            "Some photos have missing owner records; indexing stopped."
                        )
                    await uow.session.execute(
                        update(m.PhotoGuardStateModel)
                        .where(m.PhotoGuardStateModel.id == 1)
                        .values(ready=True)
                    )
                    await uow.commit()
                    print(f"PHOTO_INDEX=READY; newly_indexed={completed}", flush=True)
                    break
                image, owner = row
                stored = await uow.files.get(image.file_id)
                if stored is None:
                    raise RuntimeError(f"Photo {image.id} has no readable file record.")
                try:
                    raw = await storage.get(bucket=stored.bucket, object_key=stored.object_key)
                    prepared = await to_thread.run_sync(prepare_photo, raw)
                    del raw
                except Exception:
                    # Deliberately exclude provider error text/URLs/credentials.
                    raise RuntimeError(
                        f"Photo {image.id} could not be read. Existing data is retained; "
                        "restore this upload and rerun."
                    ) from None
                # Preserve the file ID and original object. Freeze its served key
                # so outstanding upload intents cannot mutate indexed content.
                key = f"listing_checked_legacy/{image.id}.jpg"
                thumb_key = key + "_thumb.jpg"
                await storage.put(
                    bucket=stored.bucket,
                    object_key=key,
                    data=prepared.jpeg,
                    content_type="image/jpeg",
                    # Public listing asset; keep private-document storage defaults intact.
                    server_side_encryption=False,
                )
                await storage.put(
                    bucket=stored.bucket,
                    object_key=thumb_key,
                    data=prepared.thumbnail,
                    content_type="image/jpeg",
                    # Public listing asset; keep private-document storage defaults intact.
                    server_side_encryption=False,
                )
                await uow.session.execute(
                    update(m.StoredFileModel)
                    .where(m.StoredFileModel.id == stored.id)
                    .values(
                        object_key=key,
                        mime_type="image/jpeg",
                        size_bytes=len(prepared.jpeg),
                        sha256=hashlib.sha256(prepared.jpeg).digest(),
                        width=prepared.width,
                        height=prepared.height,
                    )
                )
                await uow.session.execute(
                    update(m.ListingImageModel)
                    .where(m.ListingImageModel.id == image.id)
                    .values(
                        width=prepared.width,
                        height=prepared.height,
                        sha256=hashlib.sha256(prepared.jpeg).digest(),
                        perceptual_hash=prepared.legacy_dhash,
                        thumbnail_object_key=thumb_key,
                    )
                )
                await index.add(image.id, owner, prepared, legacy=True)
                await uow.commit()
                completed += 1
                print(f"PHOTO_INDEXED={completed}", flush=True)
            await asyncio.sleep(0.1)  # yield CPU between photos on the local laptop
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
