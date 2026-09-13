"""Reports and blocks (feature MOD-01).

Separate from `Appeal`/`ReviewCase` (`appeal.py`): those are about disputing
or triaging a *score decision*. A report is a buyer or seller flagging a
*listing, seller, or message* for staff attention - a different object, a
different queue, and a different set of reviewers may work it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from trustlens.core.domain.enums import ReportCategory, ReportStatus, ReportTargetType


@dataclass(frozen=True, slots=True)
class Report:
    """One report against a listing, seller, message, or something else.

    `target_id` is deliberately untyped beyond a UUID - what it points to is
    named by `target_type`, the same pattern `ReviewCase.related_entity_*`
    already uses, so a report is one small table rather than a family of
    near-identical ones.
    """

    id: UUID
    reporter_id: UUID
    target_type: ReportTargetType
    target_id: UUID
    category: ReportCategory
    description: str
    status: ReportStatus
    created_at: datetime
    resolved_at: datetime | None = None
    resolved_by: UUID | None = None
    resolution_note: str | None = None
    updated_at: datetime | None = None

    @property
    def is_open(self) -> bool:
        return self.status.is_open


@dataclass(frozen=True, slots=True)
class Block:
    """One user refusing further contact from another.

    Directional: `blocker_id` blocked `blocked_id`. Messaging enforcement
    checks both directions (`is_blocked_either_way`) so a blocked user
    cannot simply message from a new conversation to route around it.
    """

    id: UUID
    blocker_id: UUID
    blocked_id: UUID
    created_at: datetime


__all__ = ["Block", "Report"]
