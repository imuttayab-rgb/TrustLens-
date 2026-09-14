"""SQLAlchemy unit of work.

Owns the transaction boundary so a use case touching three aggregates still
commits once, and stages domain events on the transactional outbox in that
same transaction.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, Self
from uuid import UUID

import uuid_utils
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trustlens.core.domain.events import DomainEvent
from trustlens.core.domain.ports import (
    BlockRepository,
    FollowRepository,
    MeetingVenueRepository,
    MeetupRepository,
    MfaRecoveryCodeRepository,
    OfferRepository,
    ReportRepository,
    ReviewRepository,
    SavedSearchRepository,
    TransactionRepository,
)
from trustlens.db import models as m
from trustlens.db import repositories as repo


class SqlAlchemyUnitOfWork:
    """Transaction scope with all repositories attached.

    Usage:

        async with uow:
            ...
            await uow.publish(SomethingHappened(...))
            await uow.commit()

    Leaving the context without committing rolls back. That default is
    deliberate: a use case that raises halfway must not leave partial state.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory
        self._session: AsyncSession | None = None
        self._pending_events: list[DomainEvent] = []
        self._depth = 0

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("UnitOfWork used outside an `async with` block")
        return self._session

    async def __aenter__(self) -> Self:
        # Re-entrant: a use case that calls a helper which also opens the UoW
        # joins the outer transaction rather than opening a nested one.
        self._depth += 1
        if self._session is None:
            self._session = self._factory()
            self._bind_repositories()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._depth -= 1
        if self._depth > 0:
            return
        assert self._session is not None
        try:
            if exc_type is not None:
                await self._session.rollback()
        finally:
            await self._session.close()
            self._session = None
            self._pending_events.clear()

    def _bind_repositories(self) -> None:
        s = self.session
        self.users = repo.SqlUserRepository(s)
        self.sellers = repo.SqlSellerRepository(s)
        self.identities = repo.SqlIdentityRepository(s)
        self.phone_numbers = repo.SqlPhoneRepository(s)
        self.email_addresses = repo.SqlEmailRepository(s)
        self.devices = repo.SqlDeviceRepository(s)
        self.listings = repo.SqlListingRepository(s)
        self.favorites = repo.SqlFavoriteRepository(s)
        self.saved_searches: SavedSearchRepository = repo.SqlSavedSearchRepository(s)
        self.messaging = repo.SqlMessagingRepository(s)
        # Typed to the port, not the concrete class: unlike every other
        # repository attribute here (which mypy happens to infer as `Any`,
        # masking a real Protocol-attribute-invariance mismatch), these two
        # infer a real, specific type - which then correctly needs the exact
        # `UnitOfWork.reports`/`.blocks` interface type, not a subtype of it.
        self.reports: ReportRepository = repo.SqlReportRepository(s)
        self.blocks: BlockRepository = repo.SqlBlockRepository(s)
        self.offers: OfferRepository = repo.SqlOfferRepository(s)
        self.transactions: TransactionRepository = repo.SqlTransactionRepository(s)
        self.meeting_venues: MeetingVenueRepository = repo.SqlMeetingVenueRepository(s)
        self.meetups: MeetupRepository = repo.SqlMeetupRepository(s)
        self.follows: FollowRepository = repo.SqlFollowRepository(s)
        self.reviews: ReviewRepository = repo.SqlReviewRepository(s)
        self.trust_scores = repo.SqlTrustScoreRepository(s)
        self.scoring_models = repo.SqlScoringModelRepository(s)
        self.appeals = repo.SqlAppealRepository(s)
        self.review_cases = repo.SqlReviewCaseRepository(s)
        self.api_clients = repo.SqlApiClientRepository(s)
        self.refresh_tokens = repo.SqlRefreshTokenRepository(s)
        self.verification_tokens = repo.SqlVerificationTokenRepository(s)
        self.mfa_recovery_codes: MfaRecoveryCodeRepository = repo.SqlMfaRecoveryCodeRepository(s)
        self.otps = repo.SqlOtpRepository(s)
        self.consents = repo.SqlConsentRepository(s)
        self.files = repo.SqlFileRepository(s)
        self.notifications = repo.SqlNotificationRepository(s)
        self.audit_logs = repo.SqlAuditLogRepository(s)
        self.job_runs = repo.SqlJobRunRepository(s)

    async def publish(self, event: DomainEvent) -> None:
        """Stage a domain event on the outbox.

        Written in the SAME transaction as the state change, then relayed by a
        poller. Without this, "score updated but the webhook never fired" (or
        the reverse) is only a matter of time.
        """
        self._pending_events.append(event)
        data = event.to_outbox()
        self.session.add(
            m.OutboxEvent(
                id=UUID(str(uuid_utils.uuid7())),
                aggregate_type=data["aggregate_type"],
                aggregate_id=UUID(str(data["aggregate_id"])),
                event_type=data["event_type"],
                payload=data["payload"],
                occurred_at=data["occurred_at"],
            )
        )

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def flush(self) -> None:
        await self.session.flush()

    @property
    def collected_events(self) -> tuple[DomainEvent, ...]:
        return tuple(self._pending_events)

    # Declared so type checkers see the attributes bound in _bind_repositories.
    users: Any
    sellers: Any
    identities: Any
    phone_numbers: Any
    email_addresses: Any
    devices: Any
    listings: Any
    favorites: Any
    messaging: Any
    trust_scores: Any
    scoring_models: Any
    appeals: Any
    review_cases: Any
    api_clients: Any
    refresh_tokens: Any
    verification_tokens: Any
    otps: Any
    consents: Any
    files: Any
    notifications: Any
    audit_logs: Any
    job_runs: Any


__all__ = ["SqlAlchemyUnitOfWork"]
