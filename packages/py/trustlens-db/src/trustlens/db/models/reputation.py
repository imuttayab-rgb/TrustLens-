"""Reputation models. Preserve table names and transaction behavior across imports."""

from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from trustlens.core.domain import enums as e
from trustlens.db.base import (
    Base,
    TimestampMixin,
    uuid_fk,
    uuid_pk,
)
from .common import pg_enum


class FollowModel(Base):
    """A buyer bookmarking a seller (REP-01) - distinct from `FavoriteModel`,
    which bookmarks a listing. A plain delete on unfollow, same as favorites."""

    __tablename__ = "follows"

    id: Mapped[UUID] = uuid_pk()
    follower_id: Mapped[UUID] = uuid_fk("users.id")
    seller_id: Mapped[UUID] = uuid_fk("users.id")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("uq_follows_follower_seller", "follower_id", "seller_id", unique=True),
        Index("ix_follows_seller", "seller_id"),
    )


class ReviewModel(Base):
    """One side of a blind, transaction-scoped review (REP-01). Visibility
    is not a column here - `list_visible_for_seller` only returns a row once
    the counterpart's review for the same transaction also exists, so there
    is nothing to keep in sync when the second side is submitted."""

    __tablename__ = "reviews"

    id: Mapped[UUID] = uuid_pk()
    transaction_id: Mapped[UUID] = uuid_fk("transactions.id")
    listing_id: Mapped[UUID] = uuid_fk("listings.id")
    reviewer_id: Mapped[UUID] = uuid_fk("users.id")
    reviewee_id: Mapped[UUID] = uuid_fk("users.id")
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="review_rating_in_range"),
        Index("uq_reviews_transaction_reviewer", "transaction_id", "reviewer_id", unique=True),
        Index("ix_reviews_reviewee", "reviewee_id", "created_at"),
    )


class SignalDefinitionModel(Base, TimestampMixin):
    """The signal catalogue. Rows, not code (open/closed principle)."""

    __tablename__ = "signal_definitions"

    id: Mapped[UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    category: Mapped[e.SignalCategory] = mapped_column(
        pg_enum(e.SignalCategory, "signal_category"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    buyer_facing_description: Mapped[str] = mapped_column(Text, default="")
    max_points: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    #: Failing a critical signal clamps the score to a hard cap.
    is_critical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)


class ScoringModelRow(Base, TimestampMixin):
    __tablename__ = "scoring_models"

    id: Mapped[UUID] = uuid_pk()
    version: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    algorithm: Mapped[str] = mapped_column(String(30), nullable=False, default="WEIGHTED_SUM")
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    weights: Mapped[list[ScoringWeightModel]] = relationship(
        back_populates="model", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        # At most one active model, enforced by the database rather than by
        # application convention.
        Index(
            "uq_scoring_models_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )


class ScoringWeightModel(Base, TimestampMixin):
    __tablename__ = "scoring_weights"

    id: Mapped[UUID] = uuid_pk()
    scoring_model_id: Mapped[UUID] = uuid_fk("scoring_models.id")
    signal_definition_id: Mapped[UUID] = uuid_fk("signal_definitions.id", ondelete="RESTRICT")
    weight: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    threshold_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    hard_cap_on_fail: Mapped[int | None] = mapped_column(SmallInteger)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    model: Mapped[ScoringModelRow] = relationship(back_populates="weights")
    definition: Mapped[SignalDefinitionModel] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint("scoring_model_id", "signal_definition_id", name="uq_weight_per_signal"),
        CheckConstraint("weight >= 0", name="weight_non_negative"),
        CheckConstraint(
            "hard_cap_on_fail IS NULL OR (hard_cap_on_fail BETWEEN 0 AND 100)",
            name="cap_in_range",
        ),
    )


class TrustScoreModel(Base):
    """Immutable, append-only score computation."""

    __tablename__ = "trust_scores"

    id: Mapped[UUID] = uuid_pk()
    seller_id: Mapped[UUID] = uuid_fk("seller_profiles.id")
    scoring_model_id: Mapped[UUID] = uuid_fk("scoring_models.id", ondelete="RESTRICT")
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    risk_level: Mapped[e.RiskLevel] = mapped_column(
        pg_enum(e.RiskLevel, "risk_level"), nullable=False
    )
    raw_score: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    #: Sum of weights actually evaluated. Unavailable signals are excluded,
    #: so our provider outage never costs a seller points.
    available_weight: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    cap_applied: Mapped[int | None] = mapped_column(SmallInteger)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    trigger: Mapped[e.ScoreTrigger] = mapped_column(
        pg_enum(e.ScoreTrigger, "score_trigger"), nullable=False
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_manual_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    override_reason: Mapped[str | None] = mapped_column(Text)
    overridden_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    signals: Mapped[list[TrustScoreSignalModel]] = relationship(
        back_populates="trust_score", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 100", name="score_in_range"),
        # Overriding a computed score must always carry a written reason.
        CheckConstraint(
            "NOT is_manual_override OR override_reason IS NOT NULL",
            name="override_reason_required",
        ),
        # Exactly one current score per seller - the invariant the whole read
        # path depends on.
        Index(
            "uq_trust_scores_current",
            "seller_id",
            unique=True,
            postgresql_where=text("is_current"),
        ),
        Index("ix_trust_scores_seller_computed", "seller_id", "computed_at"),
        Index(
            "ix_trust_scores_risk_current",
            "risk_level",
            postgresql_where=text("is_current"),
        ),
    )


class TrustScoreSignalModel(Base):
    """The explainability record. This table IS the explanation."""

    __tablename__ = "trust_score_signals"

    id: Mapped[UUID] = uuid_pk()
    trust_score_id: Mapped[UUID] = uuid_fk("trust_scores.id")
    signal_definition_id: Mapped[UUID] = uuid_fk("signal_definitions.id", ondelete="RESTRICT")
    #: Denormalised so an old breakdown row survives a definition rename.
    signal_code: Mapped[str] = mapped_column(String(60), nullable=False)
    category: Mapped[e.SignalCategory] = mapped_column(
        pg_enum(e.SignalCategory, "signal_category"), nullable=False
    )
    status: Mapped[e.SignalStatus] = mapped_column(
        pg_enum(e.SignalStatus, "signal_status"), nullable=False
    )
    weight: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    points_awarded: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    points_possible: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(60), nullable=False)
    reason_text: Mapped[str] = mapped_column(Text, nullable=False)
    #: Non-PII supporting values only - this is exposed to buyers.
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    source_table: Mapped[str | None] = mapped_column(String(60))
    source_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    trust_score: Mapped[TrustScoreModel] = relationship(back_populates="signals")

    __table_args__ = (
        UniqueConstraint("trust_score_id", "signal_definition_id", name="uq_signal_per_score"),
        Index("ix_trust_score_signals_score", "trust_score_id"),
    )
