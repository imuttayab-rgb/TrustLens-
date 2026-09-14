"""Buy-now-pay-later, sandboxed (feature PAY-01).

"Sandbox" because there is no real payment gateway behind this - the spec
itself gates a real one behind legal/provider review that hasn't happened.
The platform only tracks a payment *schedule* against an existing
Transaction; money never moves through it. Marking an installment paid is
mutual-trust, the same shape `CompleteTransaction` already uses for a
handover: either party can confirm it, there is no card charge to verify
against.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from trustlens.core.application.notifications import notify
from trustlens.core.domain.entities import Installment, InstallmentPlan
from trustlens.core.domain.enums import InstallmentPlanStatus, InstallmentStatus
from trustlens.core.domain.errors import (
    EntityNotFound,
    InvalidStateError,
    PermissionDenied,
    ValidationError,
)
from trustlens.core.domain.ports import Clock, IdGenerator, UnitOfWork

MIN_INSTALLMENTS = 2
MAX_INSTALLMENTS = 12
MIN_FREQUENCY_DAYS = 7
MAX_FREQUENCY_DAYS = 90


@dataclass(frozen=True, slots=True)
class CreateInstallmentPlanCommand:
    transaction_id: UUID
    actor_id: UUID
    installment_count: int
    frequency_days: int


class CreateInstallmentPlan:
    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: CreateInstallmentPlanCommand) -> InstallmentPlan:
        if not (MIN_INSTALLMENTS <= cmd.installment_count <= MAX_INSTALLMENTS):
            raise ValidationError(
                f"Choose between {MIN_INSTALLMENTS} and {MAX_INSTALLMENTS} installments.",
                field="installmentCount",
            )
        if not (MIN_FREQUENCY_DAYS <= cmd.frequency_days <= MAX_FREQUENCY_DAYS):
            raise ValidationError(
                f"Choose a spacing between {MIN_FREQUENCY_DAYS} and {MAX_FREQUENCY_DAYS} days.",
                field="frequencyDays",
            )

        now = self._clock.now()
        async with self._uow:
            txn = await self._uow.transactions.get(cmd.transaction_id)
            if txn is None:
                raise EntityNotFound("transaction", cmd.transaction_id)
            if cmd.actor_id not in (txn.buyer_id, txn.seller_id):
                raise PermissionDenied("This transaction belongs to someone else.")
            if not txn.is_open:
                raise InvalidStateError("This transaction is already closed.")

            existing = await self._uow.installments.get_plan_for_transaction(txn.id)
            if existing is not None and existing.is_open:
                raise InvalidStateError("An installment plan already exists for this deal.")

            plan = await self._uow.installments.add_plan(
                InstallmentPlan(
                    id=self._ids.new(),
                    transaction_id=txn.id,
                    buyer_id=txn.buyer_id,
                    seller_id=txn.seller_id,
                    total_amount=txn.amount,
                    currency=txn.currency,
                    installment_count=cmd.installment_count,
                    status=InstallmentPlanStatus.ACTIVE,
                    created_at=now,
                )
            )

            for installment in _split(
                plan_id=plan.id,
                total_amount=txn.amount,
                count=cmd.installment_count,
                frequency=timedelta(days=cmd.frequency_days),
                starting_at=now,
                ids=self._ids,
                now=now,
            ):
                await self._uow.installments.add_installment(installment)

            other = txn.seller_id if cmd.actor_id == txn.buyer_id else txn.buyer_id
            await notify(
                self._uow,
                self._ids,
                self._clock,
                user_id=other,
                type="INSTALLMENT_PLAN_CREATED",
                title="Installment plan set up",
                body=(
                    f"{cmd.installment_count} payments of "
                    f"{txn.amount / cmd.installment_count:,.2f} {txn.currency} each."
                ),
                data={"transactionId": str(txn.id), "planId": str(plan.id)},
            )
            await self._uow.commit()
        return plan


def _split(
    *,
    plan_id: UUID,
    total_amount: float,
    count: int,
    frequency: timedelta,
    starting_at: datetime,
    ids: IdGenerator,
    now: datetime,
) -> list[Installment]:
    """Even shares, the last one absorbing whatever rounding leaves over -
    the same "don't lose or invent a cent" reasoning any split-the-bill
    calculation needs. The first installment is due immediately; a BNPL
    plan that made someone wait weeks for the first payment to come due
    would not actually be "buy now"."""
    base = round(total_amount / count, 2)
    installments: list[Installment] = []
    running_total = 0.0
    for i in range(count):
        is_last = i == count - 1
        amount = round(total_amount - running_total, 2) if is_last else base
        running_total += amount
        installments.append(
            Installment(
                id=ids.new(),
                plan_id=plan_id,
                sequence_number=i + 1,
                amount=amount,
                due_at=starting_at + (frequency * i),
                status=InstallmentStatus.PENDING,
                created_at=now,
            )
        )
    return installments


@dataclass(frozen=True, slots=True)
class PayInstallmentCommand:
    installment_id: UUID
    actor_id: UUID


class PayInstallment:
    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: PayInstallmentCommand) -> Installment:
        now = self._clock.now()
        async with self._uow:
            installment = await self._uow.installments.get_installment(cmd.installment_id)
            if installment is None:
                raise EntityNotFound("installment", cmd.installment_id)
            plan = await self._uow.installments.get_plan(installment.plan_id)
            if plan is None:
                raise EntityNotFound("installment_plan", installment.plan_id)
            if cmd.actor_id not in (plan.buyer_id, plan.seller_id):
                raise PermissionDenied("This installment plan belongs to someone else.")
            if not plan.is_open:
                raise InvalidStateError("This installment plan is no longer active.")
            if installment.is_paid:
                raise InvalidStateError("This installment is already paid.")

            all_installments = await self._uow.installments.list_installments(plan.id)
            # Paid in order: the first unpaid one, by sequence, is the only
            # one payable right now.
            next_due = min(
                (i for i in all_installments if not i.is_paid), key=lambda i: i.sequence_number
            )
            if next_due.id != installment.id:
                raise InvalidStateError(f"Pay installment {next_due.sequence_number} first.")

            paid = await self._uow.installments.update_installment(
                dataclasses.replace(
                    installment,
                    status=InstallmentStatus.PAID,
                    paid_at=now,
                    paid_by=cmd.actor_id,
                )
            )

            remaining = [i for i in all_installments if i.id != paid.id and not i.is_paid]
            if not remaining:
                plan = await self._uow.installments.update_plan(
                    dataclasses.replace(plan, status=InstallmentPlanStatus.COMPLETED)
                )

            other = plan.seller_id if cmd.actor_id == plan.buyer_id else plan.buyer_id
            title = "Installment paid" if remaining else "Installment plan complete"
            body = (
                f"Installment {paid.sequence_number} of {plan.installment_count} marked paid."
                if remaining
                else "All installments are now paid."
            )
            await notify(
                self._uow,
                self._ids,
                self._clock,
                user_id=other,
                type="INSTALLMENT_PAID",
                title=title,
                body=body,
                data={"transactionId": str(plan.transaction_id), "planId": str(plan.id)},
            )
            await self._uow.commit()
        return paid


@dataclass(frozen=True, slots=True)
class CancelInstallmentPlanCommand:
    plan_id: UUID
    actor_id: UUID


class CancelInstallmentPlan:
    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: CancelInstallmentPlanCommand) -> InstallmentPlan:
        now = self._clock.now()
        async with self._uow:
            plan = await self._uow.installments.get_plan(cmd.plan_id)
            if plan is None:
                raise EntityNotFound("installment_plan", cmd.plan_id)
            if cmd.actor_id not in (plan.buyer_id, plan.seller_id):
                raise PermissionDenied("This installment plan belongs to someone else.")
            if not plan.is_open:
                raise InvalidStateError("This installment plan is already closed.")

            cancelled = await self._uow.installments.update_plan(
                dataclasses.replace(plan, status=InstallmentPlanStatus.CANCELLED, cancelled_at=now)
            )
            other = plan.seller_id if cmd.actor_id == plan.buyer_id else plan.buyer_id
            await notify(
                self._uow,
                self._ids,
                self._clock,
                user_id=other,
                type="INSTALLMENT_PLAN_CANCELLED",
                title="Installment plan cancelled",
                body="The installment plan for this deal was cancelled.",
                data={"transactionId": str(plan.transaction_id), "planId": str(plan.id)},
            )
            await self._uow.commit()
        return cancelled


@dataclass(frozen=True, slots=True)
class InstallmentPlanDetail:
    plan: InstallmentPlan
    installments: tuple[Installment, ...]


class GetInstallmentPlan:
    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, transaction_id: UUID, actor_id: UUID) -> InstallmentPlanDetail | None:
        async with self._uow:
            txn = await self._uow.transactions.get(transaction_id)
            if txn is None:
                raise EntityNotFound("transaction", transaction_id)
            if actor_id not in (txn.buyer_id, txn.seller_id):
                raise PermissionDenied("This transaction belongs to someone else.")

            plan = await self._uow.installments.get_plan_for_transaction(transaction_id)
            if plan is None:
                return None
            installments = await self._uow.installments.list_installments(plan.id)
        return InstallmentPlanDetail(plan=plan, installments=tuple(installments))


__all__ = [
    "MAX_FREQUENCY_DAYS",
    "MAX_INSTALLMENTS",
    "MIN_FREQUENCY_DAYS",
    "MIN_INSTALLMENTS",
    "CancelInstallmentPlan",
    "CancelInstallmentPlanCommand",
    "CreateInstallmentPlan",
    "CreateInstallmentPlanCommand",
    "GetInstallmentPlan",
    "InstallmentPlanDetail",
    "PayInstallment",
    "PayInstallmentCommand",
]
