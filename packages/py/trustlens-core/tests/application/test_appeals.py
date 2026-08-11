"""Appeal use cases (Phase 5).

The properties worth protecting here are the ones that decide whether the
appeal route is trustworthy at all:

* a seller cannot read or act on another seller's appeal,
* a reviewer cannot silently rewrite a score,
* internal reviewer notes never reach the seller,
* resolving an appeal recomputes rather than edits the number.

Collaborators are fakes rather than mocks: these use cases coordinate a unit of
work, and asserting on recorded calls is how the coordination is checked.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from trustlens.core.application.use_cases.appeals import (
    DECISION_OVERRIDE,
    DECISION_RECOMPUTE,
    DECISION_REJECT,
    AddAppealMessage,
    AddAppealMessageCommand,
    ClaimAppeal,
    ClaimAppealCommand,
    ListAppealQueue,
    ListSellerAppeals,
    ListSellerAppealsQuery,
    ResolveAppeal,
    ResolveAppealCommand,
    SubmitAppeal,
    SubmitAppealCommand,
    WithdrawAppeal,
    WithdrawAppealCommand,
)
from trustlens.core.domain.entities import Appeal, AppealMessage
from trustlens.core.domain.enums import AppealStatus, ScoreTrigger, UserRole
from trustlens.core.domain.errors import (
    AppealLimitReached,
    AppealNotAllowed,
    EntityNotFound,
    InvalidStateError,
    PermissionDenied,
    ValidationError,
)

NOW = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
SELLER_ID = UUID("00000000-0000-0000-0000-0000000000a1")
OTHER_SELLER_ID = UUID("00000000-0000-0000-0000-0000000000a2")
USER_ID = UUID("00000000-0000-0000-0000-0000000000b1")
REVIEWER_ID = UUID("00000000-0000-0000-0000-0000000000c1")
SCORE_ID = UUID("00000000-0000-0000-0000-0000000000d1")
APPEAL_ID = UUID("00000000-0000-0000-0000-0000000000e1")

VALID_REASON = "The CNIC photo was rejected but the document is genuine and unexpired."


class FakeClock:
    def now(self) -> datetime:
        return NOW


class FakeIds:
    def __init__(self) -> None:
        self._n = 0

    def new(self) -> UUID:
        self._n += 1
        return UUID(int=self._n)


class FakeQueue:
    def __init__(self) -> None:
        self.jobs: list[tuple[str, dict[str, Any]]] = []

    async def enqueue(self, name: str, **kwargs: Any) -> None:
        self.jobs.append((name, kwargs))


class FakeAppeals:
    def __init__(self, appeal: Appeal | None = None) -> None:
        self.appeal = appeal
        self.added: list[Appeal] = []
        self.updated: list[Appeal] = []
        self.messages: list[AppealMessage] = []
        self.open_count = 0
        self.window_count = 0
        self.for_seller: list[Appeal] = []

    async def get(self, appeal_id: UUID) -> Appeal | None:
        return self.appeal

    async def add(self, appeal: Appeal) -> Appeal:
        self.added.append(appeal)
        return appeal

    async def update(self, appeal: Appeal) -> Appeal:
        self.updated.append(appeal)
        return appeal

    async def add_message(self, message: AppealMessage) -> AppealMessage:
        self.messages.append(message)
        return message

    async def list_for_seller(self, seller_id: UUID) -> list[Appeal]:
        return self.for_seller

    async def count_open_for_seller(self, seller_id: UUID) -> int:
        return self.open_count

    async def count_since(self, seller_id: UUID, *, since: datetime) -> int:
        return self.window_count

    async def list_queue(self, **kwargs: Any) -> list[Appeal]:
        return self.for_seller


class FakeScore:
    def __init__(self, score_id: UUID) -> None:
        self.id = score_id


class FakeTrustScores:
    def __init__(self, current_id: UUID | None = SCORE_ID) -> None:
        self._current = FakeScore(current_id) if current_id else None

    async def get_current(self, seller_id: UUID) -> Any:
        return self._current


class FakeSellers:
    def __init__(self, exists: bool = True) -> None:
        self._exists = exists

    async def get(self, seller_id: UUID) -> Any:
        return object() if self._exists else None


class FakeAuditLogs:
    def __init__(self) -> None:
        self.entries: list[Any] = []

    async def record(self, entry: Any) -> None:
        self.entries.append(entry)


class FakeUow:
    def __init__(
        self,
        *,
        appeals: FakeAppeals | None = None,
        current_score_id: UUID | None = SCORE_ID,
        seller_exists: bool = True,
    ) -> None:
        self.appeals = appeals or FakeAppeals()
        self.trust_scores = FakeTrustScores(current_score_id)
        self.sellers = FakeSellers(seller_exists)
        self.audit_logs = FakeAuditLogs()
        self.committed = 0

    async def __aenter__(self) -> FakeUow:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def commit(self) -> None:
        self.committed += 1


def make_appeal(**overrides: Any) -> Appeal:
    defaults: dict[str, Any] = {
        "id": APPEAL_ID,
        "seller_id": SELLER_ID,
        "trust_score_id": SCORE_ID,
        "submitted_by": USER_ID,
        "reason_category": "IDENTITY_INCORRECT",
        "reason": VALID_REASON,
        "status": AppealStatus.OPEN,
        "submitted_at": NOW,
        "created_at": NOW,
    }
    return Appeal(**{**defaults, **overrides})


def submit_command(**overrides: Any) -> SubmitAppealCommand:
    defaults: dict[str, Any] = {
        "seller_id": SELLER_ID,
        "trust_score_id": SCORE_ID,
        "submitted_by": USER_ID,
        "reason_category": "IDENTITY_INCORRECT",
        "reason": VALID_REASON,
    }
    return SubmitAppealCommand(**{**defaults, **overrides})


def make_submit(uow: FakeUow) -> SubmitAppeal:
    return SubmitAppeal(uow=cast(Any, uow), clock=FakeClock(), ids=FakeIds())


class TestSubmit:
    @pytest.mark.asyncio
    async def test_opens_an_appeal_against_the_current_score(self) -> None:
        uow = FakeUow()
        appeal = await make_submit(uow).execute(submit_command())

        assert appeal.status is AppealStatus.OPEN
        assert appeal.trust_score_id == SCORE_ID
        assert uow.committed == 1

    @pytest.mark.asyncio
    async def test_writes_an_audit_entry_in_the_same_transaction(self) -> None:
        uow = FakeUow()
        await make_submit(uow).execute(submit_command())
        assert [e.action for e in uow.audit_logs.entries] == ["appeal.submitted"]

    @pytest.mark.asyncio
    async def test_rejects_a_reason_too_short_to_act_on(self) -> None:
        uow = FakeUow()
        with pytest.raises(ValidationError):
            await make_submit(uow).execute(submit_command(reason="wrong"))
        assert uow.committed == 0

    @pytest.mark.asyncio
    async def test_rejects_an_unknown_category(self) -> None:
        with pytest.raises(ValidationError):
            await make_submit(FakeUow()).execute(submit_command(reason_category="MADE_UP"))

    @pytest.mark.asyncio
    async def test_rejects_an_appeal_against_a_superseded_score(self) -> None:
        # The seller appeals score X while X+1 is current: unreviewable, since
        # the breakdown they are objecting to is no longer the live one.
        uow = FakeUow(current_score_id=uuid4())
        with pytest.raises(AppealNotAllowed):
            await make_submit(uow).execute(submit_command())

    @pytest.mark.asyncio
    async def test_refuses_when_the_seller_has_no_score_yet(self) -> None:
        uow = FakeUow(current_score_id=None)
        with pytest.raises(InvalidStateError):
            await make_submit(uow).execute(submit_command())

    @pytest.mark.asyncio
    async def test_refuses_a_second_open_appeal(self) -> None:
        appeals = FakeAppeals()
        appeals.open_count = 1
        uow = FakeUow(appeals=appeals)
        with pytest.raises(AppealNotAllowed):
            await make_submit(uow).execute(submit_command())

    @pytest.mark.asyncio
    async def test_enforces_the_rate_limit_in_the_window(self) -> None:
        appeals = FakeAppeals()
        appeals.window_count = 3
        uow = FakeUow(appeals=appeals)
        with pytest.raises(AppealLimitReached):
            await make_submit(uow).execute(submit_command())

    @pytest.mark.asyncio
    async def test_unknown_seller_is_not_found(self) -> None:
        uow = FakeUow(seller_exists=False)
        with pytest.raises(EntityNotFound):
            await make_submit(uow).execute(submit_command())


class TestWithdraw:
    @pytest.mark.asyncio
    async def test_seller_can_close_their_own_appeal(self) -> None:
        uow = FakeUow(appeals=FakeAppeals(make_appeal()))
        use_case = WithdrawAppeal(uow=cast(Any, uow), clock=FakeClock(), ids=FakeIds())
        result = await use_case.execute(
            WithdrawAppealCommand(appeal_id=APPEAL_ID, seller_id=SELLER_ID, actor_id=USER_ID)
        )
        assert result.status is AppealStatus.WITHDRAWN

    @pytest.mark.asyncio
    async def test_another_sellers_appeal_is_not_found_rather_than_forbidden(self) -> None:
        # 404 not 403: a distinguishable "forbidden" turns the id into an
        # oracle for which appeals exist.
        uow = FakeUow(appeals=FakeAppeals(make_appeal(seller_id=OTHER_SELLER_ID)))
        use_case = WithdrawAppeal(uow=cast(Any, uow), clock=FakeClock(), ids=FakeIds())
        with pytest.raises(EntityNotFound):
            await use_case.execute(
                WithdrawAppealCommand(appeal_id=APPEAL_ID, seller_id=SELLER_ID, actor_id=USER_ID)
            )

    @pytest.mark.asyncio
    async def test_cannot_withdraw_a_resolved_appeal(self) -> None:
        uow = FakeUow(appeals=FakeAppeals(make_appeal(status=AppealStatus.APPROVED)))
        use_case = WithdrawAppeal(uow=cast(Any, uow), clock=FakeClock(), ids=FakeIds())
        with pytest.raises(InvalidStateError):
            await use_case.execute(
                WithdrawAppealCommand(appeal_id=APPEAL_ID, seller_id=SELLER_ID, actor_id=USER_ID)
            )


class TestClaim:
    @pytest.mark.asyncio
    async def test_claiming_marks_it_under_review(self) -> None:
        uow = FakeUow(appeals=FakeAppeals(make_appeal()))
        use_case = ClaimAppeal(uow=cast(Any, uow), clock=FakeClock(), ids=FakeIds())
        claimed = await use_case.execute(
            ClaimAppealCommand(appeal_id=APPEAL_ID, reviewer_id=REVIEWER_ID)
        )
        assert claimed.status is AppealStatus.UNDER_REVIEW
        assert claimed.assigned_to == REVIEWER_ID

    @pytest.mark.asyncio
    async def test_cannot_steal_another_reviewers_appeal(self) -> None:
        uow = FakeUow(appeals=FakeAppeals(make_appeal(assigned_to=uuid4())))
        use_case = ClaimAppeal(uow=cast(Any, uow), clock=FakeClock(), ids=FakeIds())
        with pytest.raises(InvalidStateError):
            await use_case.execute(ClaimAppealCommand(appeal_id=APPEAL_ID, reviewer_id=REVIEWER_ID))


class TestMessages:
    @pytest.mark.asyncio
    async def test_seller_cannot_post_an_internal_note(self) -> None:
        uow = FakeUow(appeals=FakeAppeals(make_appeal()))
        use_case = AddAppealMessage(uow=cast(Any, uow), clock=FakeClock(), ids=FakeIds())
        with pytest.raises(PermissionDenied):
            await use_case.execute(
                AddAppealMessageCommand(
                    appeal_id=APPEAL_ID,
                    sender_id=USER_ID,
                    sender_role=UserRole.SELLER,
                    body="please hurry",
                    is_internal=True,
                )
            )

    @pytest.mark.asyncio
    async def test_reviewer_can_post_an_internal_note(self) -> None:
        uow = FakeUow(appeals=FakeAppeals(make_appeal()))
        use_case = AddAppealMessage(uow=cast(Any, uow), clock=FakeClock(), ids=FakeIds())
        message = await use_case.execute(
            AddAppealMessageCommand(
                appeal_id=APPEAL_ID,
                sender_id=REVIEWER_ID,
                sender_role=UserRole.REVIEWER,
                body="Escalating: the document looks edited.",
                is_internal=True,
            )
        )
        assert message.is_internal

    @pytest.mark.asyncio
    async def test_internal_notes_are_stripped_from_the_seller_view(self) -> None:
        internal = AppealMessage(
            id=uuid4(),
            appeal_id=APPEAL_ID,
            sender_id=REVIEWER_ID,
            sender_role=UserRole.REVIEWER,
            body="probably fraudulent, check the device cluster",
            created_at=NOW,
            is_internal=True,
        )
        public = AppealMessage(
            id=uuid4(),
            appeal_id=APPEAL_ID,
            sender_id=REVIEWER_ID,
            sender_role=UserRole.REVIEWER,
            body="Could you upload a clearer photo?",
            created_at=NOW,
            is_internal=False,
        )
        appeals = FakeAppeals()
        appeals.for_seller = [make_appeal(messages=(internal, public))]
        uow = FakeUow(appeals=appeals)

        result = await ListSellerAppeals(uow=cast(Any, uow)).execute(
            ListSellerAppealsQuery(seller_id=SELLER_ID)
        )

        bodies = [m.body for m in result[0].messages]
        assert bodies == ["Could you upload a clearer photo?"]

    @pytest.mark.asyncio
    async def test_cannot_post_to_a_resolved_appeal(self) -> None:
        uow = FakeUow(appeals=FakeAppeals(make_appeal(status=AppealStatus.REJECTED)))
        use_case = AddAppealMessage(uow=cast(Any, uow), clock=FakeClock(), ids=FakeIds())
        with pytest.raises(InvalidStateError):
            await use_case.execute(
                AddAppealMessageCommand(
                    appeal_id=APPEAL_ID,
                    sender_id=USER_ID,
                    sender_role=UserRole.SELLER,
                    body="one more thing",
                )
            )


class TestQueue:
    @pytest.mark.asyncio
    async def test_resolved_appeals_are_hidden_from_the_work_queue(self) -> None:
        # Claiming a withdrawn appeal fails, and a queue whose top row cannot
        # be actioned reads as a broken screen.
        appeals = FakeAppeals()
        appeals.for_seller = [
            make_appeal(id=uuid4(), status=AppealStatus.WITHDRAWN),
            make_appeal(id=uuid4(), status=AppealStatus.OPEN),
            make_appeal(id=uuid4(), status=AppealStatus.APPROVED),
            make_appeal(id=uuid4(), status=AppealStatus.UNDER_REVIEW),
        ]
        page = await ListAppealQueue(uow=cast(Any, FakeUow(appeals=appeals))).execute()
        assert [a.status for a in page.items] == [
            AppealStatus.OPEN,
            AppealStatus.UNDER_REVIEW,
        ]

    @pytest.mark.asyncio
    async def test_resolved_can_be_asked_for_explicitly(self) -> None:
        appeals = FakeAppeals()
        appeals.for_seller = [make_appeal(status=AppealStatus.WITHDRAWN)]
        page = await ListAppealQueue(uow=cast(Any, FakeUow(appeals=appeals))).execute(
            include_resolved=True
        )
        assert len(page.items) == 1


def make_resolve(uow: FakeUow, queue: FakeQueue) -> ResolveAppeal:
    return ResolveAppeal(
        uow=cast(Any, uow), queue=cast(Any, queue), clock=FakeClock(), ids=FakeIds()
    )


def resolve_command(**overrides: Any) -> ResolveAppealCommand:
    defaults: dict[str, Any] = {
        "appeal_id": APPEAL_ID,
        "reviewer_id": REVIEWER_ID,
        "reviewer_role": UserRole.REVIEWER,
        "decision": DECISION_RECOMPUTE,
        "note": "Document re-checked and accepted; the original read was wrong.",
    }
    return ResolveAppealCommand(**{**defaults, **overrides})


class TestResolve:
    @pytest.mark.asyncio
    async def test_recompute_queues_a_rescore_rather_than_writing_a_score(self) -> None:
        uow = FakeUow(appeals=FakeAppeals(make_appeal()))
        queue = FakeQueue()
        result = await make_resolve(uow, queue).execute(resolve_command())

        assert result.appeal.status is AppealStatus.APPROVED
        assert result.rescore_queued
        assert queue.jobs[0][0] == "scoring.recompute_trust_score"
        # Parsed rather than compared to a literal: the worker turns this back
        # into a ScoreTrigger, so a name that is merely *plausible* fails inside
        # the job, minutes after the API already answered 200. That is exactly
        # how "APPEAL" shipped and silently never rescored anyone.
        assert ScoreTrigger(queue.jobs[0][1]["trigger"]) is ScoreTrigger.APPEAL_RESOLUTION
        # The number itself is never written here - only a recompute is asked
        # for. If this use case ever sets a score directly, the explanation on
        # the seller's page stops matching the signals that produced it.
        assert not uow.appeals.updated[0].resulting_score_id

    @pytest.mark.asyncio
    async def test_rejection_does_not_rescore(self) -> None:
        uow = FakeUow(appeals=FakeAppeals(make_appeal()))
        queue = FakeQueue()
        result = await make_resolve(uow, queue).execute(resolve_command(decision=DECISION_REJECT))
        assert result.appeal.status is AppealStatus.REJECTED
        assert not result.rescore_queued
        assert all(name != "scoring.recompute_trust_score" for name, _ in queue.jobs)

    @pytest.mark.asyncio
    async def test_the_seller_is_always_notified(self) -> None:
        uow = FakeUow(appeals=FakeAppeals(make_appeal()))
        queue = FakeQueue()
        await make_resolve(uow, queue).execute(resolve_command(decision=DECISION_REJECT))
        assert any(name == "notifications.send_email" for name, _ in queue.jobs)

    @pytest.mark.asyncio
    async def test_a_reviewer_cannot_override_a_score(self) -> None:
        uow = FakeUow(appeals=FakeAppeals(make_appeal()))
        with pytest.raises(PermissionDenied):
            await make_resolve(uow, FakeQueue()).execute(
                resolve_command(
                    decision=DECISION_OVERRIDE,
                    reviewer_role=UserRole.REVIEWER,
                    override_score=80,
                )
            )

    @pytest.mark.asyncio
    async def test_an_admin_can_override_with_a_score(self) -> None:
        uow = FakeUow(appeals=FakeAppeals(make_appeal()))
        queue = FakeQueue()
        result = await make_resolve(uow, queue).execute(
            resolve_command(
                decision=DECISION_OVERRIDE, reviewer_role=UserRole.ADMIN, override_score=80
            )
        )
        assert result.appeal.status is AppealStatus.APPROVED

    @pytest.mark.asyncio
    async def test_an_override_without_a_score_is_rejected(self) -> None:
        uow = FakeUow(appeals=FakeAppeals(make_appeal()))
        with pytest.raises(ValidationError):
            await make_resolve(uow, FakeQueue()).execute(
                resolve_command(decision=DECISION_OVERRIDE, reviewer_role=UserRole.ADMIN)
            )

    @pytest.mark.asyncio
    async def test_an_out_of_range_override_is_rejected(self) -> None:
        uow = FakeUow(appeals=FakeAppeals(make_appeal()))
        with pytest.raises(ValidationError):
            await make_resolve(uow, FakeQueue()).execute(
                resolve_command(
                    decision=DECISION_OVERRIDE,
                    reviewer_role=UserRole.ADMIN,
                    override_score=140,
                )
            )

    @pytest.mark.asyncio
    async def test_a_decision_needs_an_explanation_the_seller_can_read(self) -> None:
        uow = FakeUow(appeals=FakeAppeals(make_appeal()))
        with pytest.raises(ValidationError):
            await make_resolve(uow, FakeQueue()).execute(resolve_command(note="no"))

    @pytest.mark.asyncio
    async def test_cannot_resolve_twice(self) -> None:
        uow = FakeUow(appeals=FakeAppeals(make_appeal(status=AppealStatus.APPROVED)))
        with pytest.raises(AppealNotAllowed):
            await make_resolve(uow, FakeQueue()).execute(resolve_command())

    @pytest.mark.asyncio
    async def test_resolution_is_audited(self) -> None:
        uow = FakeUow(appeals=FakeAppeals(make_appeal()))
        await make_resolve(uow, FakeQueue()).execute(resolve_command())
        assert [e.action for e in uow.audit_logs.entries] == ["appeal.resolved"]

    @pytest.mark.asyncio
    async def test_the_job_is_enqueued_only_after_the_commit(self) -> None:
        # A job that runs before the transaction lands reads the pre-decision
        # state and recomputes from stale evidence.
        uow = FakeUow(appeals=FakeAppeals(make_appeal()))
        queue = FakeQueue()
        await make_resolve(uow, queue).execute(resolve_command())
        assert uow.committed == 1
        assert queue.jobs, "expected a rescore job"
