"""The admin review queue (feature F7).

Most work here is *system*-initiated: a borderline face match, an unreadable
CNIC, a device behind several accounts. Those cases exist because the
automated pipeline deliberately refused to decide - see P1-05, where an
unreadable document became PENDING rather than FAILED so a seller is never
penalised for a blurry photograph they can retake.

Two properties this module must preserve:

* **Every decision is attributable.** A human overriding an automated verdict
  changes someone's Trust Score, so the actor, the reason and the before/after
  state are written to the audit log in the same transaction as the decision.
  An audit entry written afterwards can be lost precisely when it matters.
* **A decision is not a score.** Approving a case records a verdict and
  re-triggers scoring; it never writes a score directly (ADR-0002).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from uuid import UUID

from trustlens.core.domain.entities import AuditLogEntry, ReviewCase
from trustlens.core.domain.enums import ReviewStatus, ScoreTrigger, VerificationStatus
from trustlens.core.domain.errors import EntityNotFound, InvalidStateError, ValidationError
from trustlens.core.domain.ports import Clock, IdGenerator, JobQueue, UnitOfWork

#: Terminal states. A decided case is history, not work.
_CLOSED = frozenset({ReviewStatus.APPROVED, ReviewStatus.REJECTED})

#: A reviewer overriding the machine must say why, in enough words to be
#: useful to the next person reading the audit trail - or to the seller, if
#: they appeal the decision.
MIN_DECISION_NOTE_CHARS = 10


@dataclass(frozen=True, slots=True)
class ReviewQueuePage:
    items: tuple[ReviewCase, ...]
    limit: int
    offset: int


class ListReviewQueue:
    """Oldest-highest-priority first, which the repository already orders."""

    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, *, limit: int = 50, offset: int = 0) -> ReviewQueuePage:
        bounded = max(1, min(limit, 100))
        start = max(0, offset)
        async with self._uow:
            items = await self._uow.review_cases.list_queue(limit=bounded, offset=start)
        return ReviewQueuePage(items=tuple(items), limit=bounded, offset=start)


@dataclass(frozen=True, slots=True)
class ClaimReviewCaseCommand:
    case_id: UUID
    reviewer_id: UUID


class ClaimReviewCase:
    """Assign a queued case to the reviewer about to work on it.

    Claiming is what stops two reviewers deciding the same case differently.
    A case already assigned to someone else is refused rather than silently
    reassigned.
    """

    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: ClaimReviewCaseCommand) -> ReviewCase:
        now = self._clock.now()
        async with self._uow:
            case = await self._uow.review_cases.get(cmd.case_id)
            if case is None:
                raise EntityNotFound("review_case", cmd.case_id)
            if case.status in _CLOSED:
                raise InvalidStateError("This case has already been decided.")
            if case.assigned_to is not None and case.assigned_to != cmd.reviewer_id:
                raise InvalidStateError("Another reviewer is already working on this case.")

            claimed: ReviewCase = await self._uow.review_cases.update(
                dataclasses.replace(
                    case,
                    status=ReviewStatus.ASSIGNED,
                    assigned_to=cmd.reviewer_id,
                    assigned_at=now,
                )
            )
            await self._uow.audit_logs.record(
                AuditLogEntry(
                    id=self._ids.new(),
                    action="review_case.claimed",
                    entity_type="review_cases",
                    entity_id=case.id,
                    actor_id=cmd.reviewer_id,
                    occurred_at=now,
                    before={"status": case.status.value},
                    after={"status": ReviewStatus.ASSIGNED.value},
                )
            )
            await self._uow.commit()
        return claimed


@dataclass(frozen=True, slots=True)
class DecideReviewCaseCommand:
    case_id: UUID
    reviewer_id: UUID
    approve: bool
    note: str


@dataclass(frozen=True, slots=True)
class DecideReviewCaseResult:
    case: ReviewCase
    identity_updated: bool


class DecideReviewCase:
    """Record a human verdict and let the score follow from it."""

    def __init__(self, *, uow: UnitOfWork, queue: JobQueue, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._queue = queue
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: DecideReviewCaseCommand) -> DecideReviewCaseResult:
        note = cmd.note.strip()
        if len(note) < MIN_DECISION_NOTE_CHARS:
            raise ValidationError(
                "Explain the decision in a sentence, so it can be understood later.",
                field="note",
            )

        now = self._clock.now()
        identity_updated = False

        async with self._uow:
            case = await self._uow.review_cases.get(cmd.case_id)
            if case is None:
                raise EntityNotFound("review_case", cmd.case_id)
            if case.status in _CLOSED:
                raise InvalidStateError("This case has already been decided.")

            decision = ReviewStatus.APPROVED if cmd.approve else ReviewStatus.REJECTED
            decided: ReviewCase = await self._uow.review_cases.update(
                dataclasses.replace(
                    case,
                    status=decision,
                    assigned_to=case.assigned_to or cmd.reviewer_id,
                    decision=decision.value,
                    decision_note=note,
                )
            )

            # An identity case is the one kind whose verdict changes a
            # verification record rather than only the queue.
            seller = await self._uow.sellers.get(case.seller_id)
            if seller is not None and case.related_entity_type == "identity_verifications":
                new_status = (
                    VerificationStatus.VERIFIED if cmd.approve else VerificationStatus.REJECTED
                )
                await self._uow.sellers.update(
                    dataclasses.replace(seller, identity_status=new_status, updated_at=now)
                )
                identity_updated = True

            await self._uow.audit_logs.record(
                AuditLogEntry(
                    id=self._ids.new(),
                    action="review_case.decided",
                    entity_type="review_cases",
                    entity_id=case.id,
                    actor_id=cmd.reviewer_id,
                    occurred_at=now,
                    before={"status": case.status.value},
                    # The note is stored in the audit trail as well as on the
                    # case: the case can be superseded, the audit log cannot.
                    after={"status": decision.value, "note": note},
                )
            )
            await self._uow.commit()

        # Recompute rather than adjust: the scoring policy owns the number.
        #
        # The enum member, not a string literal. This read "MANUAL_REVIEW",
        # which is not a ScoreTrigger, so the job raised ValueError *after*
        # the endpoint had already returned 200: every review decision was
        # recorded and audited, and none of them ever rescored the seller.
        await self._queue.enqueue(
            "scoring.recompute_trust_score",
            seller_id=str(case.seller_id),
            trigger=ScoreTrigger.MANUAL.value,
        )
        return DecideReviewCaseResult(case=decided, identity_updated=identity_updated)


__all__ = [
    "MIN_DECISION_NOTE_CHARS",
    "ClaimReviewCase",
    "ClaimReviewCaseCommand",
    "DecideReviewCase",
    "DecideReviewCaseCommand",
    "DecideReviewCaseResult",
    "ListReviewQueue",
    "ReviewQueuePage",
]
