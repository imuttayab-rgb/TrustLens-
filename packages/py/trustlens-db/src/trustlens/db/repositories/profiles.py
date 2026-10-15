"""Profiles repositories. Preserve table names and transaction behavior across imports."""

from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from trustlens.core.domain import entities as ent
from trustlens.db import mappers as map_
from trustlens.db import models as m
from .common import _alive


class SqlSellerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, seller_id: UUID) -> ent.SellerProfile | None:
        row = (
            await self._s.execute(
                _alive(select(m.SellerProfile), m.SellerProfile).where(
                    m.SellerProfile.id == seller_id
                )
            )
        ).scalar_one_or_none()
        return map_.to_seller(row) if row else None

    async def get_by_user(self, user_id: UUID) -> ent.SellerProfile | None:
        row = (
            await self._s.execute(
                _alive(select(m.SellerProfile), m.SellerProfile).where(
                    m.SellerProfile.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        return map_.to_seller(row) if row else None

    async def get_by_handle(self, handle: str) -> ent.SellerProfile | None:
        row = (
            await self._s.execute(
                _alive(select(m.SellerProfile), m.SellerProfile).where(
                    m.SellerProfile.handle == handle
                )
            )
        ).scalar_one_or_none()
        return map_.to_seller(row) if row else None

    async def get_by_external_ref(
        self, *, marketplace_slug: str, external_ref: str
    ) -> ent.SellerProfile | None:
        row = (
            await self._s.execute(
                _alive(select(m.SellerProfile), m.SellerProfile)
                .join(m.Marketplace, m.Marketplace.id == m.SellerProfile.marketplace_id)
                .where(
                    m.Marketplace.slug == marketplace_slug,
                    m.SellerProfile.external_seller_ref == external_ref,
                )
            )
        ).scalar_one_or_none()
        return map_.to_seller(row) if row else None

    async def create(self, seller: ent.SellerProfile) -> ent.SellerProfile:
        self._s.add(
            m.SellerProfile(
                id=seller.id,
                user_id=seller.user_id,
                handle=seller.handle,
                display_name=seller.display_name,
                account_opened_at=seller.account_opened_at,
                marketplace_id=seller.marketplace_id,
                external_seller_ref=seller.external_seller_ref,
                business_type=seller.business_type,
                city=seller.city,
                country_code=seller.country_code,
                identity_status=seller.identity_status,
                phone_status=seller.phone_status,
                email_status=seller.email_status,
                account_type=seller.account_type,
                business_legal_name=seller.business_legal_name,
                business_registration_number=seller.business_registration_number,
                business_document_file_id=seller.business_document_file_id,
                business_verification_status=seller.business_verification_status,
                created_at=seller.created_at,
                updated_at=seller.created_at,
            )
        )
        await self._s.flush()
        return seller

    async def update(self, seller: ent.SellerProfile) -> ent.SellerProfile:
        await self._s.execute(
            update(m.SellerProfile)
            .where(m.SellerProfile.id == seller.id)
            .values(
                # Names are written only by the ID-backed profile service.
                # A stale verification/score update must not restore an old name.
                business_type=seller.business_type,
                city=seller.city,
                country_code=seller.country_code,
                bio=seller.bio,
                current_trust_score_id=seller.current_trust_score_id,
                identity_status=seller.identity_status,
                phone_status=seller.phone_status,
                email_status=seller.email_status,
                account_type=seller.account_type,
                business_legal_name=seller.business_legal_name,
                business_registration_number=seller.business_registration_number,
                business_document_file_id=seller.business_document_file_id,
                business_verification_status=seller.business_verification_status,
                is_flagged=seller.is_flagged,
                version=m.SellerProfile.version + 1,
            )
        )
        return seller

    async def list_stale_scores(self, *, before: datetime, limit: int) -> list[UUID]:
        """Sellers whose current score has expired, for the nightly sweep."""
        rows = await self._s.execute(
            select(m.SellerProfile.id)
            .join(
                m.TrustScoreModel,
                (m.TrustScoreModel.seller_id == m.SellerProfile.id) & m.TrustScoreModel.is_current,
                isouter=True,
            )
            .where(
                m.SellerProfile.deleted_at.is_(None),
                (m.TrustScoreModel.id.is_(None)) | (m.TrustScoreModel.valid_until < before),
            )
            .limit(limit)
        )
        return list(rows.scalars().all())

    async def handle_exists(self, handle: str) -> bool:
        if await self._s.get(m.ProfileHandleAliasModel, handle):
            return True
        return bool(
            (
                await self._s.execute(
                    select(func.count())
                    .select_from(m.SellerProfile)
                    .where(m.SellerProfile.handle == handle)
                )
            ).scalar_one()
        )
