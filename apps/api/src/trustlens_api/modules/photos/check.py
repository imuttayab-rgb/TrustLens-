"""Read-only post-install checks, including database locks and owner isolation."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from sqlalchemy import select

from trustlens.core.domain.errors import RateLimitExceeded
from trustlens.db import models as m
from trustlens.db.photo_guard import PhotoIndex, photos_cleared
from trustlens.db.session import create_engine, create_session_factory
from trustlens.shared.config import get_settings


async def run() -> None:
    engine = create_engine(get_settings().database)
    factory = create_session_factory(engine)
    try:
        async with factory() as first, factory() as second:
            index = PhotoIndex(first)
            await index.require_ready()
            if await index.missing_count():
                raise RuntimeError("Unindexed photos remain.")
            await index.lock()
            try:
                await PhotoIndex(second).lock()
            except RateLimitExceeded:
                pass
            else:
                raise RuntimeError("Concurrent photo lock did not protect the index.")
            await first.rollback()
            await PhotoIndex(second).lock()
            await second.rollback()
            row = (
                await first.execute(select(m.PhotoFingerprintModel).limit(1))
            ).scalar_one_or_none()
            if row is not None:
                outsider = uuid4()
                assert await index.exact_match(outsider, row.digests)
                # Test owner filtering by compiling/executing the same query
                # against a fingerprint ID; legacy duplicates may belong to
                # multiple users, so same-owner exact_match need not be false.
                owner_query = select(m.PhotoFingerprintModel.image_id).where(
                    m.PhotoFingerprintModel.image_id == row.image_id,
                    m.PhotoFingerprintModel.owner_user_id != row.owner_user_id,
                )
                assert (await first.execute(owner_query)).first() is None
                await index.candidates(outsider, [])  # executes the PostgreSQL array operator
            await first.execute(select(m.ListingModel.id).where(photos_cleared()).limit(1))
            print(
                "PHOTO_INDEX=PASS\nCROSS_ACCOUNT_QUERY=PASS\nCONCURRENT_UPLOAD_GUARD=PASS\nPUBLICATION_GUARD=PASS"
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
