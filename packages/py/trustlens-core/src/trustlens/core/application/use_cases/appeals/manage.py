"""Appeals (feature F8, Phase 5).

An appeal is the answer to the question a scoring system must always be able
to answer: *"this is wrong, and what can I do about it?"* The proposal's
promise is an **explainable** score, and explainability without recourse is
just a nicer error message. This module is the recourse.

Three properties it must preserve.

* **An appeal names one computation, not "my score".** `trust_score_id` is
  required. Scores are recomputed on a schedule and on every signal change, so
  "my score is wrong" is unreviewable by the time a human reads it; *that*
  computation, with its breakdown frozen, is reproducible.
* **Resolving never writes a score.** Approving an appeal corrects the
  underlying evidence and re-triggers scoring, or records an explicit,
  expiring override. It never edits the number directly (ADR-0002) - otherwise
  the score stops being a function of its signals and the explanation on the
  seller's page becomes a lie.
* **Every transition is attributable.** Actor, timestamp and before/after go
  into the audit log inside the same transaction as the change.

Rate limiting lives in `AppealPolicy`, not here: how many appeals are
reasonable is a business rule, and the FYP is examined on those being legible.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from trustlens.core.domain.entities import Appeal, AppealMessage, AuditLogEntry
from trustlens.core.domain.enums import AppealStatus, ScoreTrigger, UserRole
from trustlens.core.domain.errors import (
    EntityNotFound,
    InvalidStateError,
    PermissionDenied,
    ValidationError,
)
from trustlens.core.domain.policies import AppealPolicy
from trustlens.core.domain.ports import Clock, IdGenerator, JobQueue, UnitOfWork

#: A seller must say enough for a reviewer to act on it. "wrong" is not an
#: appeal; it produces a rejection and a second appeal saying the same thing.
MIN_REASON_CHARS = 20
MAX_REASON_CHARS = 4000

#: What a reviewer may decide. RECOMPUTE is the default and the honest one:
#: the evidence was corrected, so the engine runs again and the number follows.
#: OVERRIDE exists because some corrections cannot be expressed as evidence
#: (a signal provider was wrong and cannot be re-queried), and it is deliberately
#: uncomfortable: admin-only, reason required, and it expires.
DECISION_RECOMPUTE = "RECOMPUTE"
DECISION_OVERRIDE = "OVERRIDE"
DECISION_REJECT = "REJECT"

DECISIONS = frozenset({DECISION_RECOMPUTE, DECISION_OVERRIDE, DECISION_REJECT})

#: An override that never expires is a permanent lie about a live signal.
OVERRIDE_EXPIRY_DAYS = 90

#: Categories a seller can pick. Free text alone makes triage impossible;
#: the category routes the appeal, the text explains it.
REASON_CATEGORIES = frozenset(
    {
        "IDENTITY_INCORRECT",
        "PHONE_INCORRECT",
        "LISTING_MISJUDGED",
        "DEVICE_INCORRECT",
        "OTHER",
    }
)


@dataclass(frozen=True, slots=True)
class SubmitAppealCommand:
    seller_id: UUID
    trust_score_id: UUID
    submitted_by: UUID
    reason_category: str
    reason: str


class SubmitAppeal:
    """Open an appeal against one specific score computation."""

    def __init__(
        self,
        *,
        uow: UnitOfWork,
        clock: Clock,
        ids: IdGenerator,
        policy: AppealPolicy | None = None,
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids
        self._policy = policy or AppealPolicy()

    async def execute(self, cmd: SubmitAppealCommand) -> Appeal:
        reason = cmd.reason.strip()
        if len(reason) < MIN_REASON_CHARS:
            raise ValidationError(
                "Explain what is wrong in at least "
                f"{MIN_REASON_CHARS} characters, so a reviewer can act on it.",
                field="reason",
            )
        if len(reason) > MAX_REASON_CHARS:
            raise ValidationError("That explanation is too long.", field="reason")
        if cmd.reason_category not in REASON_CATEGORIES:
            raise ValidationError("Choose a reason category.", field="reasonCategory")

        now = self._clock.now()

        async with self._uow:
            seller = await self._uow.sellers.get(cmd.seller_id)
            if seller is None:
                raise EntityNotFound("seller_profile", cmd.seller_id)

            # Only the *current* computation is appealable. Appealing a
            # superseded one wastes a reviewer's time on a number nobody sees.
            current = await self._uow.trust_scores.get_current(cmd.seller_id)
            score_is_current = current is not None and current.id == cmd.trust_score_id
            if current is None:
                raise InvalidStateError(
                    "You do not have a Trust Score yet, so there is nothing to appeal."
                )

            open_appeals = await self._uow.appeals.count_open_for_seller(cmd.seller_id)
            window_start = now - timedelta(days=self._policy.window_days)
            in_window = await self._uow.appeals.count_since(cmd.seller_id, since=window_start)

            # Raises AppealNotAllowed / AppealLimitReached, which the API maps
            # to 409 and 429 respectively.
            self._policy.assert_can_submit(
                open_appeals=open_appeals,
                appeals_in_window=in_window,
                score_is_current=score_is_current,
            )

            appeal = await self._uow.appeals.add(
                Appeal(
                    id=self._ids.new(),
                    seller_id=cmd.seller_id,
                    trust_score_id=cmd.trust_score_id,
                    submitted_by=cmd.submitted_by,
                    reason_category=cmd.reason_category,
                    reason=reason,
                    status=AppealStatus.OPEN,
                    submitted_at=now,
                    created_at=now,
                )
            )
            await self._uow.audit_logs.record(
                AuditLogEntry(
                    id=self._ids.new(),
                    action="appeal.submitted",
                    entity_type="appeals",
                    entity_id=appeal.id,
                    actor_id=cmd.submitted_by,
                    occurred_at=now,
                    before=None,
                    after={
                        "status": AppealStatus.OPEN.value,
                        "trust_score_id": str(cmd.trust_score_id),
                        "reason_category": cmd.reason_category,
                    },
                )
            )
            await self._uow.commit()

        return appeal


@dataclass(frozen=True, slots=True)
class ListSellerAppealsQuery:
    seller_id: UUID


class ListSellerAppeals:
    """A seller's own appeals, newest first.

    Internal reviewer notes are stripped: `is_internal` messages exist so
    reviewers can discuss a case without that discussion becoming a reply to
    the seller.
    """

    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, query: ListSellerAppealsQuery) -> tuple[Appeal, ...]:
        async with self._uow:
            appeals = await self._uow.appeals.list_for_seller(query.seller_id)
        return tuple(_without_internal_messages(a) for a in appeals)


@dataclass(frozen=True, slots=True)
class WithdrawAppealCommand:
    appeal_id: UUID
    seller_id: UUID
    actor_id: UUID


class WithdrawAppeal:
    """Let a seller close their own appeal.

    Without this, the one-open-appeal limit becomes a trap: a seller who
    appeals in haste cannot appeal properly until a reviewer gets to it.
    """

    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: WithdrawAppealCommand) -> Appeal:
        now = self._clock.now()
        async with self._uow:
            appeal = await self._uow.appeals.get(cmd.appeal_id)
            if appeal is None:
                raise EntityNotFound("appeal", cmd.appeal_id)
            # Checked rather than filtered in the query: an appeal belonging to
            # another seller must not be distinguishable from one that does not
            # exist, or the id becomes an enumeration oracle.
            if appeal.seller_id != cmd.seller_id:
                raise EntityNotFound("appeal", cmd.appeal_id)
            if not appeal.is_open:
                raise InvalidStateError("This appeal has already been resolved.")

            withdrawn: Appeal = await self._uow.appeals.update(
                dataclasses.replace(
                    appeal,
                    status=AppealStatus.WITHDRAWN,
                    resolved_at=now,
                    resolved_by=cmd.actor_id,
                )
            )
            await self._uow.audit_logs.record(
                AuditLogEntry(
                    id=self._ids.new(),
                    action="appeal.withdrawn",
                    entity_type="appeals",
                    entity_id=appeal.id,
                    actor_id=cmd.actor_id,
                    occurred_at=now,
                    before={"status": appeal.status.value},
                    after={"status": AppealStatus.WITHDRAWN.value},
                )
            )
            await self._uow.commit()
        return withdrawn


@dataclass(frozen=True, slots=True)
class AppealQueuePage:
    items: tuple[Appeal, ...]
    limit: int
    offset: int


class ListAppealQueue:
    """The reviewer queue: oldest first, so nothing starves.

    Resolved and withdrawn appeals are excluded unless a status is asked for
    explicitly. A queue is a list of work, and a reviewer who opens it should
    not have to guess which rows are still actionable - claiming a withdrawn
    appeal fails, and failing on the top row reads as a broken screen.
    """

    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        *,
        status: AppealStatus | None = None,
        include_resolved: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> AppealQueuePage:
        bounded = max(1, min(limit, 100))
        start = max(0, offset)
        async with self._uow:
            items = await self._uow.appeals.list_queue(status=status, limit=bounded, offset=start)
        # The repository filters on one exact status; "still open" spans three,
        # so the set is narrowed here rather than adding a second query path.
        if status is None and not include_resolved:
            items = [a for a in items if a.is_open]
        return AppealQueuePage(items=tuple(items), limit=bounded, offset=start)


@dataclass(frozen=True, slots=True)
class ClaimAppealCommand:
    appeal_id: UUID
    reviewer_id: UUID


class ClaimAppeal:
    """Assign an appeal to the reviewer about to work on it."""

    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: ClaimAppealCommand) -> Appeal:
        now = self._clock.now()
        async with self._uow:
            appeal = await self._uow.appeals.get(cmd.appeal_id)
            if appeal is None:
                raise EntityNotFound("appeal", cmd.appeal_id)
            if not appeal.is_open:
                raise InvalidStateError("This appeal has already been resolved.")
            if appeal.assigned_to is not None and appeal.assigned_to != cmd.reviewer_id:
                raise InvalidStateError("Another reviewer is already working on this appeal.")

            claimed: Appeal = await self._uow.appeals.update(
                dataclasses.replace(
                    appeal,
                    status=AppealStatus.UNDER_REVIEW,
                    assigned_to=cmd.reviewer_id,
                    assigned_at=now,
                )
            )
            await self._uow.audit_logs.record(
                AuditLogEntry(
                    id=self._ids.new(),
                    action="appeal.claimed",
                    entity_type="appeals",
                    entity_id=appeal.id,
                    actor_id=cmd.reviewer_id,
                    occurred_at=now,
                    before={"status": appeal.status.value},
                    after={"status": AppealStatus.UNDER_REVIEW.value},
                )
            )
            await self._uow.commit()
        return claimed


@dataclass(frozen=True, slots=True)
class AddAppealMessageCommand:
    appeal_id: UUID
    sender_id: UUID
    sender_role: UserRole
    body: str
    is_internal: bool = False
    #: Set for a seller reply so the appeal cannot be read by another account.
    seller_id: UUID | None = None


class AddAppealMessage:
    """Post a message on an appeal.

    This is what makes NEEDS_INFO usable: a reviewer asks for a clearer
    photograph, the seller replies, and the thread stays attached to the case.
    """

    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: AddAppealMessageCommand) -> AppealMessage:
        body = cmd.body.strip()
        if not body:
            raise ValidationError("Write a message before sending.", field="body")

        # A seller must never be able to write a note only reviewers can see.
        if cmd.is_internal and cmd.sender_role not in {UserRole.REVIEWER, UserRole.ADMIN}:
            raise PermissionDenied("Only reviewers can add internal notes.")

        now = self._clock.now()
        async with self._uow:
            appeal = await self._uow.appeals.get(cmd.appeal_id)
            if appeal is None:
                raise EntityNotFound("appeal", cmd.appeal_id)
            if cmd.seller_id is not None and appeal.seller_id != cmd.seller_id:
                raise EntityNotFound("appeal", cmd.appeal_id)
            if not appeal.is_open:
                raise InvalidStateError("This appeal has been resolved and is now read-only.")

            message = await self._uow.appeals.add_message(
                AppealMessage(
                    id=self._ids.new(),
                    appeal_id=appeal.id,
                    sender_id=cmd.sender_id,
                    sender_role=cmd.sender_role,
                    body=body,
                    created_at=now,
                    is_internal=cmd.is_internal,
                )
            )
            await self._uow.commit()
        return message


@dataclass(frozen=True, slots=True)
class ResolveAppealCommand:
    appeal_id: UUID
    reviewer_id: UUID
    reviewer_role: UserRole
    decision: str
    note: str
    #: Only meaningful for OVERRIDE.
    override_score: int | None = None


@dataclass(frozen=True, slots=True)
class ResolveAppealResult:
    appeal: Appeal
    rescore_queued: bool


class ResolveAppeal:
    """Record a reviewer's decision and let the score follow from it."""

    def __init__(
        self,
        *,
        uow: UnitOfWork,
        queue: JobQueue,
        clock: Clock,
        ids: IdGenerator,
        policy: AppealPolicy | None = None,
    ) -> None:
        self._uow = uow
        self._queue = queue
        self._clock = clock
        self._ids = ids
        self._policy = policy or AppealPolicy()

    async def execute(self, cmd: ResolveAppealCommand) -> ResolveAppealResult:
        note = cmd.note.strip()
        if cmd.decision not in DECISIONS:
            raise ValidationError("Unknown decision.", field="decision")
        if len(note) < MIN_REASON_CHARS:
            raise ValidationError(
                "Explain the decision - the seller reads this.",
                field="note",
            )
        # An override bypasses the evidence, so it is the one decision that
        # needs a rank above reviewer.
        if cmd.decision == DECISION_OVERRIDE and cmd.reviewer_role is not UserRole.ADMIN:
            raise PermissionDenied("Only an admin can override a score.")
        if cmd.decision == DECISION_OVERRIDE and cmd.override_score is None:
            raise ValidationError("An override needs a score.", field="overrideScore")
        if cmd.override_score is not None and not 0 <= cmd.override_score <= 100:
            raise ValidationError("A score is between 0 and 100.", field="overrideScore")

        now = self._clock.now()

        async with self._uow:
            appeal = await self._uow.appeals.get(cmd.appeal_id)
            if appeal is None:
                raise EntityNotFound("appeal", cmd.appeal_id)
            self._policy.assert_can_resolve(appeal.status)

            status = (
                AppealStatus.REJECTED if cmd.decision == DECISION_REJECT else AppealStatus.APPROVED
            )
            resolved: Appeal = await self._uow.appeals.update(
                dataclasses.replace(
                    appeal,
                    status=status,
                    assigned_to=appeal.assigned_to or cmd.reviewer_id,
                    decision=cmd.decision,
                    resolution_note=note,
                    resolved_at=now,
                    resolved_by=cmd.reviewer_id,
                )
            )

            await self._uow.audit_logs.record(
                AuditLogEntry(
                    id=self._ids.new(),
                    action="appeal.resolved",
                    entity_type="appeals",
                    entity_id=appeal.id,
                    actor_id=cmd.reviewer_id,
                    occurred_at=now,
                    before={"status": appeal.status.value},
                    after={
                        "status": status.value,
                        "decision": cmd.decision,
                        "note": note,
                        **(
                            {"override_score": cmd.override_score}
                            if cmd.override_score is not None
                            else {}
                        ),
                    },
                )
            )
            await self._uow.commit()

        # Enqueued after commit: a job that runs before the transaction lands
        # would read the pre-decision state.
        rescore_queued = cmd.decision in {DECISION_RECOMPUTE, DECISION_OVERRIDE}
        if rescore_queued:
            await self._queue.enqueue(
                "scoring.recompute_trust_score",
                seller_id=str(appeal.seller_id),
                # The enum member, not a string literal: the worker parses this
                # back into a ScoreTrigger, and a name that does not exist there
                # fails *inside the job*, long after this call returned 200.
                trigger=ScoreTrigger.APPEAL_RESOLUTION.value,
            )

        await self._queue.enqueue(
            "notifications.send_email",
            to_user_id=str(appeal.submitted_by),
            template="appeal_resolved",
            context={"decision": cmd.decision.lower(), "note": note},
        )

        return ResolveAppealResult(appeal=resolved, rescore_queued=rescore_queued)


def _without_internal_messages(appeal: Appeal) -> Appeal:
    """Strip reviewer-only notes before a seller sees the thread."""
    visible = tuple(m for m in appeal.messages if not m.is_internal)
    return dataclasses.replace(appeal, messages=visible)


__all__ = [
    "DECISIONS",
    "DECISION_OVERRIDE",
    "DECISION_RECOMPUTE",
    "DECISION_REJECT",
    "MAX_REASON_CHARS",
    "MIN_REASON_CHARS",
    "OVERRIDE_EXPIRY_DAYS",
    "REASON_CATEGORIES",
    "AddAppealMessage",
    "AddAppealMessageCommand",
    "AppealQueuePage",
    "ClaimAppeal",
    "ClaimAppealCommand",
    "ListAppealQueue",
    "ListSellerAppeals",
    "ListSellerAppealsQuery",
    "ResolveAppeal",
    "ResolveAppealCommand",
    "ResolveAppealResult",
    "SubmitAppeal",
    "SubmitAppealCommand",
    "WithdrawAppeal",
    "WithdrawAppealCommand",
]
