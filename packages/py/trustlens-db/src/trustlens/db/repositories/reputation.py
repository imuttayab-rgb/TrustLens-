"""Reputation repositories. Preserve table names and transaction behavior across imports."""

from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload
from trustlens.core.domain import entities as ent
from trustlens.db import mappers as map_
from trustlens.db import models as m


class SqlFollowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, follow: ent.Follow) -> ent.Follow:
        self._s.add(
            m.FollowModel(
                id=follow.id,
                follower_id=follow.follower_id,
                seller_id=follow.seller_id,
                created_at=follow.created_at,
            )
        )
        await self._s.flush()
        return follow

    async def remove(self, *, follower_id: UUID, seller_id: UUID) -> None:
        await self._s.execute(
            delete(m.FollowModel).where(
                m.FollowModel.follower_id == follower_id, m.FollowModel.seller_id == seller_id
            )
        )

    async def exists(self, *, follower_id: UUID, seller_id: UUID) -> bool:
        row = (
            await self._s.execute(
                select(m.FollowModel.id).where(
                    m.FollowModel.follower_id == follower_id,
                    m.FollowModel.seller_id == seller_id,
                )
            )
        ).first()
        return row is not None

    async def list_followed_seller_ids(self, follower_id: UUID) -> frozenset[UUID]:
        rows = await self._s.execute(
            select(m.FollowModel.seller_id).where(m.FollowModel.follower_id == follower_id)
        )
        return frozenset(rows.scalars().all())

    async def count_followers(self, seller_id: UUID) -> int:
        result = await self._s.execute(
            select(func.count(m.FollowModel.id)).where(m.FollowModel.seller_id == seller_id)
        )
        return int(result.scalar_one())


class SqlReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @staticmethod
    def _counterpart_exists() -> Any:
        """The blind-reveal rule as a correlated subquery: a review is
        visible once a row exists for the same transaction with reviewer
        and reviewee swapped."""
        counterpart = aliased(m.ReviewModel)
        return (
            select(counterpart.id)
            .where(
                counterpart.transaction_id == m.ReviewModel.transaction_id,
                counterpart.reviewer_id == m.ReviewModel.reviewee_id,
                counterpart.reviewee_id == m.ReviewModel.reviewer_id,
            )
            .correlate(m.ReviewModel)
            .exists()
        )

    async def add(self, review: ent.Review) -> ent.Review:
        self._s.add(
            m.ReviewModel(
                id=review.id,
                transaction_id=review.transaction_id,
                listing_id=review.listing_id,
                reviewer_id=review.reviewer_id,
                reviewee_id=review.reviewee_id,
                rating=review.rating,
                comment=review.comment,
                created_at=review.created_at,
            )
        )
        await self._s.flush()
        return review

    async def get_by_transaction_and_reviewer(
        self, transaction_id: UUID, reviewer_id: UUID
    ) -> ent.Review | None:
        stmt = select(m.ReviewModel).where(
            m.ReviewModel.transaction_id == transaction_id,
            m.ReviewModel.reviewer_id == reviewer_id,
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return map_.to_review(row) if row else None

    async def list_for_transaction(self, transaction_id: UUID) -> list[ent.Review]:
        stmt = (
            select(m.ReviewModel)
            .where(m.ReviewModel.transaction_id == transaction_id)
            .order_by(m.ReviewModel.created_at.asc())
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [map_.to_review(r) for r in rows]

    async def list_visible_for_seller(
        self, seller_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[ent.Review]:
        stmt = (
            select(m.ReviewModel)
            .where(
                m.ReviewModel.reviewee_id == seller_id,
                self._counterpart_exists(),
            )
            .order_by(m.ReviewModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [map_.to_review(r) for r in rows]

    async def get_rating_summary(self, seller_id: UUID) -> ent.SellerRatingSummary:
        stmt = select(func.avg(m.ReviewModel.rating), func.count(m.ReviewModel.id)).where(
            m.ReviewModel.reviewee_id == seller_id,
            self._counterpart_exists(),
        )
        average, count = (await self._s.execute(stmt)).one()
        return ent.SellerRatingSummary(
            seller_id=seller_id,
            average_rating=float(average) if average is not None else None,
            review_count=int(count),
        )


class SqlTrustScoreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def _version_of(self, model_id: UUID) -> str:
        return (
            await self._s.execute(
                select(m.ScoringModelRow.version).where(m.ScoringModelRow.id == model_id)
            )
        ).scalar_one()

    async def get(self, score_id: UUID) -> ent.TrustScore | None:
        row = await self._s.get(m.TrustScoreModel, score_id)
        if row is None:
            return None
        return map_.to_trust_score(row, model_version=await self._version_of(row.scoring_model_id))

    async def get_current(self, seller_id: UUID) -> ent.TrustScore | None:
        row = (
            await self._s.execute(
                select(m.TrustScoreModel)
                .options(selectinload(m.TrustScoreModel.signals))
                .where(m.TrustScoreModel.seller_id == seller_id, m.TrustScoreModel.is_current)
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return map_.to_trust_score(row, model_version=await self._version_of(row.scoring_model_id))

    async def replace_current(self, score: ent.TrustScore) -> ent.TrustScore:
        """Demote the previous score and insert the new one, atomically.

        The demote MUST happen before the insert: `uq_trust_scores_current` is
        a partial unique index, and inserting first would violate it.
        """
        await self._s.execute(
            update(m.TrustScoreModel)
            .where(m.TrustScoreModel.seller_id == score.seller_id, m.TrustScoreModel.is_current)
            .values(is_current=False)
        )
        await self._s.flush()

        row = m.TrustScoreModel(
            id=score.id,
            seller_id=score.seller_id,
            scoring_model_id=score.scoring_model_id,
            score=int(score.score),
            risk_level=score.risk_level,
            raw_score=score.raw_score,
            available_weight=score.available_weight,
            cap_applied=score.cap_applied,
            confidence=float(score.confidence),
            trigger=score.trigger,
            is_current=True,
            is_manual_override=score.is_manual_override,
            override_reason=score.override_reason,
            overridden_by=score.overridden_by,
            computed_at=score.computed_at,
            valid_until=score.valid_until,
        )
        self._s.add(row)
        for signal in score.signals:
            self._s.add(
                m.TrustScoreSignalModel(
                    id=signal.id,
                    trust_score_id=score.id,
                    signal_definition_id=signal.signal_definition_id,
                    signal_code=signal.signal_code.value,
                    category=signal.category,
                    status=signal.status,
                    weight=signal.weight,
                    points_awarded=signal.points_awarded,
                    points_possible=signal.points_possible,
                    confidence=signal.confidence,
                    reason_code=signal.reason_code.value,
                    reason_text=signal.reason_text,
                    evidence=signal.evidence,
                    source_table=signal.source_table,
                    source_id=signal.source_id,
                )
            )
        await self._s.flush()
        return score

    async def list_history(
        self, seller_id: UUID, *, limit: int = 20, before: datetime | None = None
    ) -> list[ent.TrustScore]:
        stmt = (
            select(m.TrustScoreModel)
            .options(selectinload(m.TrustScoreModel.signals))
            .where(m.TrustScoreModel.seller_id == seller_id)
            .order_by(m.TrustScoreModel.computed_at.desc())
            .limit(limit)
        )
        if before is not None:
            stmt = stmt.where(m.TrustScoreModel.computed_at < before)
        rows = (await self._s.execute(stmt)).scalars().all()
        return [
            map_.to_trust_score(r, model_version=await self._version_of(r.scoring_model_id))
            for r in rows
        ]


class SqlScoringModelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_active(self) -> ent.ScoringModel | None:
        row = (
            await self._s.execute(
                select(m.ScoringModelRow)
                .options(
                    selectinload(m.ScoringModelRow.weights).selectinload(
                        m.ScoringWeightModel.definition
                    )
                )
                .where(m.ScoringModelRow.is_active)
            )
        ).scalar_one_or_none()
        return map_.to_scoring_model(row) if row else None

    async def get(self, model_id: UUID) -> ent.ScoringModel | None:
        row = (
            await self._s.execute(
                select(m.ScoringModelRow)
                .options(
                    selectinload(m.ScoringModelRow.weights).selectinload(
                        m.ScoringWeightModel.definition
                    )
                )
                .where(m.ScoringModelRow.id == model_id)
            )
        ).scalar_one_or_none()
        return map_.to_scoring_model(row) if row else None

    async def get_by_version(self, version: str) -> ent.ScoringModel | None:
        row = (
            await self._s.execute(
                select(m.ScoringModelRow)
                .options(
                    selectinload(m.ScoringModelRow.weights).selectinload(
                        m.ScoringWeightModel.definition
                    )
                )
                .where(m.ScoringModelRow.version == version)
            )
        ).scalar_one_or_none()
        return map_.to_scoring_model(row) if row else None

    async def list_all(self) -> list[ent.ScoringModel]:
        rows = await self._s.execute(
            select(m.ScoringModelRow)
            .options(
                selectinload(m.ScoringModelRow.weights).selectinload(
                    m.ScoringWeightModel.definition
                )
            )
            .order_by(m.ScoringModelRow.created_at.desc())
        )
        return [map_.to_scoring_model(r) for r in rows.scalars().all()]

    async def list_signal_definitions(self) -> list[ent.SignalDefinition]:
        rows = await self._s.execute(
            select(m.SignalDefinitionModel).order_by(m.SignalDefinitionModel.display_order)
        )
        return [map_.to_signal_definition(r) for r in rows.scalars().all()]

    async def create(self, model: ent.ScoringModel) -> ent.ScoringModel:
        self._s.add(
            m.ScoringModelRow(
                id=model.id,
                version=model.version,
                name=model.name,
                description=model.description,
                is_active=False,  # activation is a separate, audited action
                algorithm=model.algorithm,
                config=model.config,
            )
        )
        for weight in model.weights:
            self._s.add(
                m.ScoringWeightModel(
                    id=weight.id,
                    scoring_model_id=model.id,
                    signal_definition_id=weight.signal_definition_id,
                    weight=weight.weight,
                    threshold_config=weight.threshold_config,
                    hard_cap_on_fail=weight.hard_cap_on_fail,
                    is_enabled=weight.is_enabled,
                )
            )
        await self._s.flush()
        return model

    async def update(self, model: ent.ScoringModel) -> ent.ScoringModel:
        await self._s.execute(
            update(m.ScoringModelRow)
            .where(m.ScoringModelRow.id == model.id)
            .values(name=model.name, description=model.description, config=model.config)
        )
        for weight in model.weights:
            await self._s.execute(
                update(m.ScoringWeightModel)
                .where(m.ScoringWeightModel.id == weight.id)
                .values(
                    weight=weight.weight,
                    threshold_config=weight.threshold_config,
                    hard_cap_on_fail=weight.hard_cap_on_fail,
                    is_enabled=weight.is_enabled,
                )
            )
        return model

    async def activate(self, model_id: UUID, *, by: UUID, at: datetime) -> ent.ScoringModel:
        # Deactivate first: uq_scoring_models_active is a partial unique index
        # and would reject two active rows even momentarily.
        await self._s.execute(
            update(m.ScoringModelRow).where(m.ScoringModelRow.is_active).values(is_active=False)
        )
        await self._s.flush()
        await self._s.execute(
            update(m.ScoringModelRow)
            .where(m.ScoringModelRow.id == model_id)
            .values(is_active=True, activated_at=at, activated_by=by)
        )
        await self._s.flush()
        model = await self.get(model_id)
        assert model is not None
        return model
