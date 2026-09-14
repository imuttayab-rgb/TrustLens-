"""Read paths for the trust score, including the public (PII-free) projection.

The public projection is built here rather than in the transport layer so that
"no PII in the public API" is a property of the domain, not a convention a
future contributor has to remember.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from uuid import UUID

from trustlens.core.domain.entities import SellerProfile, SignalDefinition, TrustScore
from trustlens.core.domain.enums import (
    RiskLevel,
    ScoreTrigger,
    SellerAccountType,
    SignalCategory,
    SignalCode,
    SignalStatus,
)
from trustlens.core.domain.errors import EntityNotFound
from trustlens.core.domain.policies import band_label, rank_improvements
from trustlens.core.domain.ports import Cache, Clock, JobQueue, UnitOfWork


@dataclass(frozen=True, slots=True)
class PublicReason:
    code: str
    impact: str
    text: str
    #: Which signal family this reason belongs to, so a reader can group and
    #: label reasons rather than guessing from the code. Not PII - it names a
    #: category of check, never a value that was checked.
    #:
    #: Defaulted because this field was added after payloads were already in
    #: the score cache; an entry written before the change deserialises
    #: without it rather than raising for the length of one cache TTL.
    category: str = ""


@dataclass(frozen=True, slots=True)
class PublicTrustScore:
    """What a partner marketplace or an anonymous buyer may see.

    Deliberately contains no email, phone, CNIC, image URL or seller name -
    the schema simply has no such field, so a future change cannot leak one by
    accident.
    """

    seller_ref: str
    score: int
    risk_level: str
    risk_label: str
    confidence: float
    verifications: dict[str, str]
    reasons: list[PublicReason]
    model_version: str
    computed_at: str
    expires_at: str
    unavailable_signals: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class GetPublicTrustScoreCommand:
    #: A TrustLens id, a handle, or "{marketplace_slug}:{external_ref}".
    seller_ref: str


class GetPublicTrustScore:
    """Cache-aside read of a seller's public score.

    p95 target is 150 ms, which is only achievable because the score is
    *precomputed*: this path never scores anything, it looks one up.
    """

    def __init__(
        self,
        *,
        uow: UnitOfWork,
        cache: Cache,
        clock: Clock,
        queue: JobQueue,
        cache_ttl_seconds: int = 300,
    ) -> None:
        self._uow = uow
        self._cache = cache
        self._clock = clock
        self._queue = queue
        self._ttl = cache_ttl_seconds

    async def execute(self, cmd: GetPublicTrustScoreCommand) -> tuple[PublicTrustScore, bool]:
        """Returns (payload, was_cached)."""
        cache_key = f"score:ref:{cmd.seller_ref}"
        if cached := await self._cache.get(cache_key):
            return _public_from_json(cached), True

        async with self._uow:
            seller = await self._resolve_seller(cmd.seller_ref)
            if seller is None:
                raise EntityNotFound("seller", cmd.seller_ref)

            score = await self._uow.trust_scores.get_current(seller.id)
            definitions = {
                d.code: d for d in await self._uow.scoring_models.list_signal_definitions()
            }

        if score is None:
            payload = _unscored_payload(cmd.seller_ref, seller)
            # No score yet: kick off a computation so the next call succeeds,
            # rather than making every future request miss identically.
            await self._queue.enqueue(
                "scoring.recompute_trust_score",
                seller_id=str(seller.id),
                trigger=ScoreTrigger.API_REQUEST.value,
            )
        else:
            payload = to_public(cmd.seller_ref, score, seller, definitions)
            if score.is_stale_at(self._clock.now()):
                await self._queue.enqueue(
                    "scoring.recompute_trust_score",
                    seller_id=str(seller.id),
                    trigger=ScoreTrigger.API_REQUEST.value,
                )

        await self._cache.set(cache_key, payload.to_json(), ttl_seconds=self._ttl)
        return payload, False

    async def _resolve_seller(self, ref: str) -> SellerProfile | None:
        if ":" in ref:
            marketplace_slug, _, external_ref = ref.partition(":")
            return await self._uow.sellers.get_by_external_ref(
                marketplace_slug=marketplace_slug, external_ref=external_ref
            )
        try:
            return await self._uow.sellers.get(UUID(ref))
        except ValueError:
            return await self._uow.sellers.get_by_handle(ref)


def _public_verifications(seller: SellerProfile) -> dict[str, str]:
    verifications = {
        "identity": seller.identity_status.value,
        "phone": seller.phone_status.value,
        "email": seller.email_status.value,
    }
    # Only shown for a business account (BUS-01) - an individual seller's
    # storefront has no reason to show a "business: NOT_STARTED" row.
    if seller.account_type == SellerAccountType.BUSINESS:
        verifications["business"] = seller.business_verification_status.value
    return verifications


def to_public(
    seller_ref: str,
    score: TrustScore,
    seller: SellerProfile,
    definitions: dict[SignalCode, SignalDefinition],
) -> PublicTrustScore:
    reasons = [
        PublicReason(
            code=signal.reason_code.value,
            impact="NEGATIVE" if signal.points_lost > 0 else "POSITIVE",
            category=signal.category.value,
            text=(
                definitions[signal.signal_code].buyer_facing_description
                if signal.signal_code in definitions and not signal.reason_text
                else signal.reason_text
            ),
        )
        for signal in score.top_reasons(limit=6)
    ]
    return PublicTrustScore(
        seller_ref=seller_ref,
        score=int(score.score),
        risk_level=score.risk_level.value,
        risk_label=band_label(score.risk_level),
        confidence=float(score.confidence),
        verifications=_public_verifications(seller),
        reasons=reasons,
        model_version=score.scoring_model_version,
        computed_at=score.computed_at.isoformat(),
        expires_at=score.valid_until.isoformat(),
        unavailable_signals=[c.value for c in score.unavailable_signal_codes],
    )


def _unscored_payload(seller_ref: str, seller: SellerProfile) -> PublicTrustScore:
    """A seller with no score yet is UNKNOWN, never HIGH risk."""
    now = seller.created_at
    return PublicTrustScore(
        seller_ref=seller_ref,
        score=0,
        risk_level=RiskLevel.UNKNOWN.value,
        risk_label=band_label(RiskLevel.UNKNOWN),
        confidence=0.0,
        verifications=_public_verifications(seller),
        reasons=[
            PublicReason(
                code="INSUFFICIENT_EVIDENCE",
                impact="NEUTRAL",
                category=SignalCategory.IDENTITY.value,
                text="This seller has not completed enough checks to be scored yet.",
            )
        ],
        model_version="-",
        computed_at=now.isoformat(),
        expires_at=now.isoformat(),
    )


def _public_from_json(raw: str) -> PublicTrustScore:
    data = json.loads(raw)
    data["reasons"] = [PublicReason(**r) for r in data.get("reasons", [])]
    return PublicTrustScore(**data)


# ── Full breakdown (authenticated) ───────────────────────────────────


@dataclass(frozen=True, slots=True)
class Improvement:
    signal_code: str
    points_available: float
    action: str


@dataclass(frozen=True, slots=True)
class GetTrustScoreCommand:
    seller_id: UUID
    include_improvements: bool = True


@dataclass(frozen=True, slots=True)
class TrustScoreDetail:
    score: TrustScore
    improvements: tuple[Improvement, ...] = ()


class GetTrustScore:
    """The seller's / admin's view: full breakdown plus a ranked fix list."""

    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, cmd: GetTrustScoreCommand) -> TrustScoreDetail:
        async with self._uow:
            score = await self._uow.trust_scores.get_current(cmd.seller_id)
            if score is None:
                raise EntityNotFound("trust_score", cmd.seller_id)

            if not cmd.include_improvements:
                return TrustScoreDetail(score=score)

            definitions = {
                d.code: d for d in await self._uow.scoring_models.list_signal_definitions()
            }

        ranked = rank_improvements(score.signals, definitions, limit=5)
        return TrustScoreDetail(
            score=score,
            improvements=tuple(
                Improvement(signal_code=code.value, points_available=points, action=action)
                for code, points, action in ranked
            ),
        )


def summarise(score: TrustScore) -> str:
    """One-line human summary, built from rule output only.

    An LLM may rephrase this for the buyer-facing page, but it is generated
    deterministically first so the system still explains itself when the
    provider is down.
    """
    if score.risk_level == RiskLevel.UNKNOWN:
        return "Not enough checks have been completed to judge this seller."

    passed = [s for s in score.signals if s.status == SignalStatus.PASS]
    failed = [s for s in score.signals if s.status == SignalStatus.FAIL]

    parts: list[str] = []
    if passed:
        parts.append(f"{len(passed)} of {len(passed) + len(failed)} checks passed.")
    if failed:
        worst = max(failed, key=lambda s: s.points_lost)
        parts.append(worst.reason_text)
    return " ".join(parts) or band_label(score.risk_level)


__all__ = [
    "GetPublicTrustScore",
    "GetPublicTrustScoreCommand",
    "GetTrustScore",
    "GetTrustScoreCommand",
    "Improvement",
    "PublicReason",
    "PublicTrustScore",
    "TrustScoreDetail",
    "summarise",
    "to_public",
]
