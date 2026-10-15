"""Revoke verified identities whose ID card has since expired.

A seller verified with a card valid today may keep trading after the card
lapses. This sweep moves such sellers from VERIFIED to EXPIRED, which:

* closes the publication gate, so their ACTIVE listings go back to private
  drafts in the same transaction (public queries also re-check at read time);
* lets the seller resubmit with a renewed card (StartIdentityVerification only
  blocks PROCESSING and VERIFIED);
* is written to the audit log with status values only - never the date,
  number or name.

Evidence rules live in services/identity_expiry.py: real OCR only, documents
of the latest verification only. One transaction per seller, so one bad row
cannot block the rest of the sweep.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from uuid import UUID

from trustlens.core.application.services.identity_expiry import (
    SIMULATED_OCR_ENGINES,
    lapsed_expiry,
)
from trustlens.core.application.services.listing_publication import sync_listing_publication
from trustlens.core.domain.entities import AuditLogEntry
from trustlens.core.domain.enums import ScoreTrigger, VerificationStatus
from trustlens.core.domain.ports import Clock, IdGenerator, JobQueue, UnitOfWork

SWEEP_BATCH_LIMIT = 500


@dataclass(frozen=True, slots=True)
class ExpireLapsedIdentitiesResult:
    checked: int
    expired: int
    listings_withheld: int


class ExpireLapsedIdentities:
    def __init__(self, *, uow: UnitOfWork, queue: JobQueue, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._queue = queue
        self._clock = clock
        self._ids = ids

    async def execute(self) -> ExpireLapsedIdentitiesResult:
        today = self._clock.now().date()
        async with self._uow:
            # A cheap, indexed pre-filter; each candidate is re-checked below
            # against its LATEST verification inside its own transaction.
            candidates = await self._uow.identities.list_verified_sellers_with_lapsed_id(
                today=today,
                excluded_engines=tuple(sorted(SIMULATED_OCR_ENGINES)),
                limit=SWEEP_BATCH_LIMIT,
            )
        expired = withheld = 0
        for seller_id in candidates:
            changed, hidden = await self._expire_one(seller_id)
            expired += int(changed)
            withheld += hidden
        return ExpireLapsedIdentitiesResult(
            checked=len(candidates), expired=expired, listings_withheld=withheld
        )

    async def _expire_one(self, seller_id: UUID) -> tuple[bool, int]:
        current_time = self._clock.now()
        async with self._uow:
            seller = await self._uow.sellers.get(seller_id)
            if seller is None or seller.identity_status != VerificationStatus.VERIFIED:
                return False, 0
            verification = await self._uow.identities.get_latest_verification(seller.id)
            documents = await self._uow.identities.list_documents(seller.id)
            if lapsed_expiry(verification, documents, current_time.date()) is None:
                return False, 0
            updated = await self._uow.sellers.update(
                dataclasses.replace(
                    seller, identity_status=VerificationStatus.EXPIRED, updated_at=current_time
                )
            )
            _, hidden = await sync_listing_publication(self._uow, updated, now=current_time)
            await self._uow.audit_logs.record(
                AuditLogEntry(
                    id=self._ids.new(),
                    action="identity.document_expired",
                    entity_type="seller_profiles",
                    entity_id=seller.id,
                    actor_id=None,  # system sweep, not a person
                    occurred_at=current_time,
                    before={"identity_status": VerificationStatus.VERIFIED.value},
                    after={
                        "identity_status": VerificationStatus.EXPIRED.value,
                        "listings_withheld": hidden,
                        "evidence": "real_ocr_expiry_passed",
                    },
                )
            )
            await self._uow.commit()
        # After commit: the score must stop crediting a lapsed identity.
        await self._queue.enqueue(
            "scoring.recompute_trust_score",
            seller_id=str(seller_id),
            trigger=ScoreTrigger.SIGNAL_CHANGE.value,
        )
        return True, hidden


__all__ = ["SWEEP_BATCH_LIMIT", "ExpireLapsedIdentities", "ExpireLapsedIdentitiesResult"]
