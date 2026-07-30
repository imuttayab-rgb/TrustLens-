"""ComputeTrustScore - the central use case.

Invoked only by a domain event (never inline in a request handler), so every
signal change recomputes through exactly one code path:

    IdentityVerified / PhoneVerified / ListingAnalysed / ScoringModelActivated
        -> enqueue "scoring.recompute_trust_score"
            -> ComputeTrustScore.execute()

Concurrency: a per-seller Redis lock plus a queue-level debounce collapses a
burst of verification events into a single computation and guarantees two runs
can never race to set `is_current`.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from trustlens.core.application.services.signal_collector import (
    SellerEvidence,
    SignalCollector,
)
from trustlens.core.domain.entities import SellerProfile, SignalDefinition, TrustScore
from trustlens.core.domain.enums import ScoreTrigger, SignalCode
from trustlens.core.domain.errors import EntityNotFound, NoActiveScoringModel
from trustlens.core.domain.events import TrustScoreComputed
from trustlens.core.domain.policies import FreshnessPolicy, ScoringPolicy
from trustlens.core.domain.ports import Cache, Clock, IdGenerator, UnitOfWork


@dataclass(frozen=True, slots=True)
class ComputeTrustScoreCommand:
    seller_id: UUID
    trigger: ScoreTrigger = ScoreTrigger.SIGNAL_CHANGE
    #: Skip when a fresh score already exists. Used by the nightly sweep and
    #: the public-API cache-miss path; an explicit recompute request does not.
    skip_if_fresh: bool = False


@dataclass(frozen=True, slots=True)
class ComputeTrustScoreResult:
    trust_score: TrustScore
    recomputed: bool
    previous_score: int | None = None


class ComputeTrustScore:
    """Gathers evidence, prices it against the active model, persists the result."""

    LOCK_TTL_SECONDS = 60

    def __init__(
        self,
        *,
        uow: UnitOfWork,
        collector: SignalCollector,
        cache: Cache,
        clock: Clock,
        ids: IdGenerator,
        freshness: FreshnessPolicy | None = None,
        min_evidence_weight: float = 40.0,
    ) -> None:
        self._uow = uow
        self._collector = collector
        self._cache = cache
        self._clock = clock
        self._ids = ids
        self._freshness = freshness or FreshnessPolicy()
        self._min_evidence_weight = min_evidence_weight

    async def execute(self, cmd: ComputeTrustScoreCommand) -> ComputeTrustScoreResult:
        lock_key = f"lock:score:{cmd.seller_id}"
        acquired = await self._cache.acquire_lock(lock_key, ttl_seconds=self.LOCK_TTL_SECONDS)

        if not acquired:
            # Another worker is already scoring this seller. Returning the
            # current score is correct - the in-flight run supersedes it.
            async with self._uow:
                existing = await self._uow.trust_scores.get_current(cmd.seller_id)
            if existing is not None:
                return ComputeTrustScoreResult(existing, recomputed=False)

        try:
            return await self._compute(cmd)
        finally:
            if acquired:
                await self._cache.release_lock(lock_key)

    async def _compute(self, cmd: ComputeTrustScoreCommand) -> ComputeTrustScoreResult:
        now = self._clock.now()

        async with self._uow:
            seller = await self._uow.sellers.get(cmd.seller_id)
            if seller is None:
                raise EntityNotFound("seller", cmd.seller_id)

            previous = await self._uow.trust_scores.get_current(cmd.seller_id)
            if self._can_skip(cmd, previous, now):
                assert previous is not None
                return ComputeTrustScoreResult(previous, recomputed=False)

            model = await self._uow.scoring_models.get_active()
            if model is None:
                raise NoActiveScoringModel

            definitions: dict[SignalCode, SignalDefinition] = {
                d.code: d for d in await self._uow.scoring_models.list_signal_definitions()
            }

            evidence = await self._gather_evidence(seller, now)
            evaluations = self._collector.collect(evidence)

            policy = ScoringPolicy(
                model, definitions, min_evidence_weight=self._min_evidence_weight
            )
            computation = policy.evaluate(evaluations)

            score_id = self._ids.new()
            trust_score = TrustScore(
                id=score_id,
                seller_id=cmd.seller_id,
                scoring_model_id=model.id,
                scoring_model_version=model.version,
                score=computation.score,
                risk_level=computation.risk_level,
                raw_score=computation.raw_score,
                available_weight=computation.available_weight,
                confidence=computation.confidence,
                trigger=cmd.trigger,
                computed_at=now,
                valid_until=self._freshness.valid_until(now),
                signals=tuple(
                    dataclasses.replace(signal, id=self._ids.new(), trust_score_id=score_id)
                    for signal in computation.signals
                ),
                cap_applied=computation.cap_applied,
                is_current=True,
            )

            saved = await self._uow.trust_scores.replace_current(trust_score)

            await self._uow.sellers.update(
                dataclasses.replace(seller, current_trust_score_id=saved.id, updated_at=now)
            )

            await self._uow.publish(
                TrustScoreComputed.build(
                    seller_id=cmd.seller_id,
                    score=int(saved.score),
                    risk_level=saved.risk_level,
                    previous_score=int(previous.score) if previous else None,
                    trigger=cmd.trigger,
                    model_version=model.version,
                    occurred_at=now,
                )
            )

            await self._uow.commit()

        # Invalidate AFTER commit: clearing first would let a concurrent read
        # repopulate the cache from a transaction that then rolls back.
        await self._cache.delete_pattern(f"score:{cmd.seller_id}:*")
        await self._cache.delete(f"seller:{cmd.seller_id}:summary")

        return ComputeTrustScoreResult(
            trust_score=saved,
            recomputed=True,
            previous_score=int(previous.score) if previous else None,
        )

    def _can_skip(
        self, cmd: ComputeTrustScoreCommand, previous: TrustScore | None, now: datetime
    ) -> bool:
        return (
            cmd.skip_if_fresh
            and previous is not None
            and not previous.is_stale_at(now)
            # A manual override must still be re-evaluated on its own schedule
            # so a one-off human decision cannot become permanent by accident.
            and not previous.is_manual_override
        )

    async def _gather_evidence(self, seller: SellerProfile, now: datetime) -> SellerEvidence:
        """One pass over the repositories, so scoring itself stays pure."""
        uow = self._uow

        documents = tuple(await uow.identities.list_documents(seller.id))
        verification = await uow.identities.get_latest_verification(seller.id)
        phone = await uow.phone_numbers.get_primary(seller.user_id)
        email = await uow.email_addresses.get_primary(seller.user_id)
        analyses = tuple(await uow.listings.latest_analyses_for_seller(seller.id, limit=20))
        devices = await uow.devices.list_for_user(seller.user_id)
        access_events = await uow.devices.list_recent_access(seller.user_id, limit=200)

        cnic_hash = next((d.extracted_cnic_hash for d in documents if d.extracted_cnic_hash), None)
        duplicate_accounts = (
            await uow.identities.count_sellers_with_cnic_hash(
                cnic_hash, excluding_seller_id=seller.id
            )
            if cnic_hash is not None
            else 0
        )

        phone_reuse = (
            await uow.phone_numbers.count_users_with_number(
                phone.e164, excluding_user_id=seller.user_id
            )
            if phone is not None
            else 0
        )

        cutoff = now - timedelta(days=30)
        active_days = len({e.occurred_at.date() for e in access_events if e.occurred_at >= cutoff})

        ip_reputation = None
        for event in access_events:
            if event.ip:
                ip_reputation = await uow.devices.get_ip_reputation(event.ip)
                if ip_reputation is not None:
                    break

        return SellerEvidence(
            seller=seller,
            now=now,
            identity_documents=documents,
            identity_verification=verification,
            duplicate_cnic_accounts=duplicate_accounts,
            phone=phone,
            phone_reuse_accounts=phone_reuse,
            email=email,
            linked_device_accounts=await uow.devices.count_accounts_sharing_devices(seller.user_id),
            has_emulator_device=any(d.is_emulator or d.is_bot for d in devices),
            has_banned_shared_device=await uow.devices.has_banned_account_on_shared_device(
                seller.user_id
            ),
            device_evidence_available=bool(devices),
            ip_reputation=ip_reputation,
            recent_access_days=active_days,
            listing_count=await uow.listings.count_for_seller(seller.id),
            listing_analyses=analyses,
        )


__all__ = ["ComputeTrustScore", "ComputeTrustScoreCommand", "ComputeTrustScoreResult"]
