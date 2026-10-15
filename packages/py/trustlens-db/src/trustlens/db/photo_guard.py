"""Transactional photo index and fail-closed publication predicate."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from trustlens.core.domain.errors import RateLimitExceeded
from trustlens.db import models as m

# One image processor across API processes; try-lock returns immediately, so
# waiting clients don't allocate image buffers or exhaust the connection pool.
PHOTO_LOCK = 847392105
MAX_CANDIDATES = 128


def photos_cleared() -> ColumnElement[bool]:
    missing = (
        select(m.ListingImageModel.id)
        .outerjoin(
            m.PhotoFingerprintModel, m.PhotoFingerprintModel.image_id == m.ListingImageModel.id
        )
        .where(
            m.ListingImageModel.listing_id == m.ListingModel.id,
            m.PhotoFingerprintModel.image_id.is_(None),
        )
        .correlate(m.ListingModel)
        .exists()
    )
    return ~missing


class PhotoIndex:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock(self) -> None:
        acquired = (
            await self.session.execute(
                text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": PHOTO_LOCK}
            )
        ).scalar_one()
        if not acquired:
            raise RateLimitExceeded(
                "Another photo is being checked. Please retry in a few seconds.", retry_after=3
            )

    async def require_ready(self) -> None:
        ready = await self.session.get(m.PhotoGuardStateModel, 1)
        if ready is None or not ready.ready:
            raise RateLimitExceeded(
                "Existing photos are still being indexed. Please retry shortly.", retry_after=15
            )

    async def exact_match(self, owner: UUID, digests: list[str]) -> bool:
        query = (
            select(m.PhotoFingerprintModel.image_id)
            .where(
                m.PhotoFingerprintModel.owner_user_id != owner,
                m.PhotoFingerprintModel.digests.op("&&")(digests),
            )
            .limit(1)
        )
        return (await self.session.execute(query)).first() is not None

    async def candidates(self, owner: UUID, bands: list[str]) -> list[dict[str, Any]]:
        query = (
            select(m.PhotoFingerprintModel.fingerprint)
            .where(
                m.PhotoFingerprintModel.owner_user_id != owner,
                m.PhotoFingerprintModel.bands.op("&&")(bands),
            )
            .distinct()
            .limit(MAX_CANDIDATES + 1)
        )
        candidates = list((await self.session.execute(query)).scalars())
        if len(candidates) > MAX_CANDIDATES:
            # Never silently truncate the shortlist and pass an unchecked copy.
            raise RateLimitExceeded(
                "This photo has too many similar matches to check safely. "
                "Try a clear, close-up photo with a different background.",
                retry_after=15,
            )
        return candidates

    async def add(
        self, image_id: UUID, owner: UUID, prepared: Any, *, legacy: bool = False
    ) -> None:
        self.session.add(
            m.PhotoFingerprintModel(
                image_id=image_id,
                owner_user_id=owner,
                fingerprint=prepared.fingerprint,
                bands=prepared.bands,
                digests=prepared.digests,
                legacy=legacy,
            )
        )
        await self.session.flush()

    async def missing_count(self) -> int:
        query = (
            select(func.count())
            .select_from(m.ListingImageModel)
            .outerjoin(
                m.PhotoFingerprintModel, m.PhotoFingerprintModel.image_id == m.ListingImageModel.id
            )
            .where(m.PhotoFingerprintModel.image_id.is_(None))
        )
        return int((await self.session.execute(query)).scalar_one())
