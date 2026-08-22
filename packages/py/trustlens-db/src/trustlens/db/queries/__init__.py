"""Read-optimized query models for administrative screens."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from trustlens.core.domain.enums import RiskLevel
from trustlens.db import models as m


@dataclass(frozen=True, slots=True)
class SellerSearchRow:
    id: UUID
    handle: str
    display_name: str
    email: str
    city: str | None
    identity_status: str
    phone_status: str
    email_status: str
    is_flagged: bool
    score: int | None
    risk_level: str | None
    updated_at: object


class SellerAdminQueries:
    """Single-query seller list for the admin panel."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _statement(
        self,
        *,
        search: str | None,
        risk_level: RiskLevel | None,
        flagged: bool | None,
    ) -> Select[tuple[object, ...]]:
        stmt = (
            select(
                m.SellerProfile.id,
                m.SellerProfile.handle,
                m.SellerProfile.display_name,
                m.User.email,
                m.SellerProfile.city,
                m.SellerProfile.identity_status,
                m.SellerProfile.phone_status,
                m.SellerProfile.email_status,
                m.SellerProfile.is_flagged,
                m.TrustScoreModel.score,
                m.TrustScoreModel.risk_level,
                m.SellerProfile.updated_at,
            )
            .join(m.User, m.User.id == m.SellerProfile.user_id)
            .join(
                m.TrustScoreModel,
                and_(
                    m.TrustScoreModel.seller_id == m.SellerProfile.id,
                    m.TrustScoreModel.is_current,
                ),
                isouter=True,
            )
            .where(m.SellerProfile.deleted_at.is_(None), m.User.deleted_at.is_(None))
        )
        if search:
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    m.SellerProfile.handle.ilike(term),
                    m.SellerProfile.display_name.ilike(term),
                    m.User.email.ilike(term),
                )
            )
        if risk_level is not None:
            stmt = stmt.where(m.TrustScoreModel.risk_level == risk_level)
        if flagged is not None:
            stmt = stmt.where(m.SellerProfile.is_flagged == flagged)
        return stmt

    async def search(
        self,
        *,
        search: str | None,
        risk_level: RiskLevel | None,
        flagged: bool | None,
        limit: int,
        offset: int,
    ) -> tuple[list[SellerSearchRow], int]:
        base = self._statement(search=search, risk_level=risk_level, flagged=flagged)
        total = int(
            (
                await self._session.execute(select(func.count()).select_from(base.subquery()))
            ).scalar_one()
        )
        rows = (
            await self._session.execute(
                base.order_by(m.SellerProfile.updated_at.desc(), m.SellerProfile.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
        return [SellerSearchRow(*row) for row in rows], total

    async def get(self, seller_id: UUID) -> SellerSearchRow | None:
        row = (
            await self._session.execute(
                self._statement(search=None, risk_level=None, flagged=None).where(
                    m.SellerProfile.id == seller_id
                )
            )
        ).first()
        return SellerSearchRow(*row) if row else None


__all__ = ["SellerAdminQueries", "SellerSearchRow"]
