"""Repository ports.

One repository per aggregate, not one generic `Repository[T]` - interface
segregation, and it keeps each contract small enough to fake honestly.

Repositories return **domain entities**, never ORM rows. That mapping at the
repository edge is what keeps SQLAlchemy out of trustlens.core, and what makes
the in-memory fakes in tests behaviourally equivalent to the real thing.

Read-heavy admin screens deliberately bypass these and use hand-written query
models (trustlens.db.queries): forcing every read through an aggregate
repository is the classic cause of N+1 death in admin panels.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from trustlens.core.domain.entities import (
        AccessEvent,
        ApiClient,
        ApiKey,
        Appeal,
        AppealMessage,
        AuditLogEntry,
        Block,
        Consent,
        Conversation,
        ConversationSummary,
        Device,
        DeviceLink,
        EmailAddress,
        Favorite,
        Follow,
        IdentityDocument,
        IdentityVerification,
        IpReputation,
        JobRun,
        Listing,
        ListingAnalysis,
        MeetingVenue,
        Meetup,
        Message,
        Notification,
        Offer,
        OtpCode,
        PhoneNumber,
        PublicListingDetail,
        PublicListingSummary,
        RefreshToken,
        Report,
        Review,
        ReviewCase,
        ScoringModel,
        SellerProfile,
        SellerRatingSummary,
        SignalDefinition,
        StoredFile,
        Transaction,
        TrustScore,
        User,
        VerificationToken,
    )
    from trustlens.core.domain.enums import (
        AppealStatus,
        MeetupStatus,
        OfferStatus,
        OtpPurpose,
        ReportStatus,
        TokenPurpose,
        TransactionStatus,
    )
    from trustlens.core.domain.value_objects import Email, PhoneE164


@runtime_checkable
class UserRepository(Protocol):
    async def get(self, user_id: UUID) -> User | None: ...

    async def get_by_email(self, email: Email) -> User | None: ...

    async def get_password_hash(self, user_id: UUID) -> str | None: ...

    async def create(self, *, user: User, password_hash: str | None) -> User: ...

    async def update(self, user: User) -> User: ...

    async def set_password_hash(self, user_id: UUID, password_hash: str) -> None: ...

    async def get_mfa_secret(self, user_id: UUID) -> bytes | None:
        """The encrypted TOTP secret (BLK-04) - kept off the `User` entity
        entirely, the same reasoning `get_password_hash` already follows for
        the password hash: a secret that must be decrypted to be used has no
        business round-tripping through a dataclass that gets logged,
        serialised, or handed to code that has no reason to see it."""
        ...

    async def set_mfa_secret(self, user_id: UUID, secret_encrypted: bytes | None) -> None:
        """`None` clears it - disabling MFA (or a fresh, unconfirmed
        enrollment overwriting a stale one) with nothing left to decrypt."""
        ...

    async def record_failed_login(
        self, user_id: UUID, *, locked_until: datetime | None
    ) -> None: ...

    async def record_successful_login(self, user_id: UUID, *, at: datetime) -> None: ...

    async def mark_email_verified(self, user_id: UUID, *, at: datetime) -> None: ...

    async def assign_role(
        self, user_id: UUID, role_key: str, *, granted_by: UUID | None
    ) -> None: ...

    async def list_permissions(self, user_id: UUID) -> frozenset[str]: ...


@runtime_checkable
class SellerRepository(Protocol):
    async def get(self, seller_id: UUID) -> SellerProfile | None: ...

    async def get_by_user(self, user_id: UUID) -> SellerProfile | None: ...

    async def get_by_handle(self, handle: str) -> SellerProfile | None: ...

    async def get_by_external_ref(
        self, *, marketplace_slug: str, external_ref: str
    ) -> SellerProfile | None: ...

    async def create(self, seller: SellerProfile) -> SellerProfile: ...

    async def update(self, seller: SellerProfile) -> SellerProfile: ...

    async def list_stale_scores(self, *, before: datetime, limit: int) -> list[UUID]: ...

    async def handle_exists(self, handle: str) -> bool: ...


@runtime_checkable
class IdentityRepository(Protocol):
    async def get_document(self, document_id: UUID) -> IdentityDocument | None: ...

    async def list_documents(self, seller_id: UUID) -> list[IdentityDocument]: ...

    async def add_document(self, document: IdentityDocument) -> IdentityDocument: ...

    async def update_document(self, document: IdentityDocument) -> IdentityDocument: ...

    async def get_latest_verification(self, seller_id: UUID) -> IdentityVerification | None: ...

    async def get_latest_verification_by_id(
        self, verification_id: UUID
    ) -> IdentityVerification | None: ...

    async def add_verification(
        self, verification: IdentityVerification
    ) -> IdentityVerification: ...

    async def update_verification(
        self, verification: IdentityVerification
    ) -> IdentityVerification: ...

    async def count_sellers_with_cnic_hash(
        self, cnic_hash: bytes, *, excluding_seller_id: UUID | None = None
    ) -> int:
        """Duplicate-CNIC detection: one national ID across many accounts.

        Runs against an index on the HMAC, so the CNIC number itself stays
        encrypted at rest while the fraud pattern is still detectable.
        """
        ...


@runtime_checkable
class PhoneNumberRepository(Protocol):
    async def get(self, phone_id: UUID) -> PhoneNumber | None: ...

    async def get_primary(self, user_id: UUID) -> PhoneNumber | None: ...

    async def list_for_user(self, user_id: UUID) -> list[PhoneNumber]: ...

    async def add(self, phone: PhoneNumber) -> PhoneNumber: ...

    async def update(self, phone: PhoneNumber) -> PhoneNumber: ...

    async def count_users_with_number(
        self, e164: PhoneE164, *, excluding_user_id: UUID | None = None
    ) -> int: ...


@runtime_checkable
class EmailAddressRepository(Protocol):
    async def get_primary(self, user_id: UUID) -> EmailAddress | None: ...

    async def list_for_user(self, user_id: UUID) -> list[EmailAddress]: ...

    async def add(self, email: EmailAddress) -> EmailAddress: ...

    async def update(self, email: EmailAddress) -> EmailAddress: ...


@runtime_checkable
class DeviceRepository(Protocol):
    async def get_by_fingerprint(self, fingerprint_hash: bytes) -> Device | None: ...

    async def upsert(self, device: Device) -> Device: ...

    async def link(self, link: DeviceLink) -> DeviceLink: ...

    async def list_for_user(self, user_id: UUID) -> list[Device]: ...

    async def count_accounts_sharing_devices(self, user_id: UUID) -> int:
        """The "multiple accounts from one device" detector."""
        ...

    async def has_banned_account_on_shared_device(self, user_id: UUID) -> bool: ...

    async def record_access(self, event: AccessEvent) -> None: ...

    async def list_recent_access(self, user_id: UUID, *, limit: int) -> list[AccessEvent]: ...

    async def get_ip_reputation(self, ip: str) -> IpReputation | None: ...

    async def upsert_ip_reputation(self, reputation: IpReputation) -> IpReputation: ...


@runtime_checkable
class ListingRepository(Protocol):
    async def get(self, listing_id: UUID) -> Listing | None: ...

    async def list_for_seller(
        self, seller_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> list[Listing]: ...

    async def count_for_seller(self, seller_id: UUID) -> int: ...

    async def add(self, listing: Listing) -> Listing: ...

    async def update(self, listing: Listing) -> Listing: ...

    async def add_analysis(self, analysis: ListingAnalysis) -> ListingAnalysis: ...

    async def latest_analyses_for_seller(
        self, seller_id: UUID, *, limit: int = 20
    ) -> list[ListingAnalysis]: ...

    async def category_median_price(self, category: str, *, currency: str) -> float | None: ...

    async def get_public_detail(self, listing_id: UUID) -> PublicListingDetail | None:
        """The full "view this listing" page - every image, the
        description, still no seller contact details. Only ever returns an
        ACTIVE listing; anything else is treated as not found."""
        ...

    async def search_public(
        self,
        *,
        category: str | None = None,
        q: str | None = None,
        city: str | None = None,
        area: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        seller_handle: str | None = None,
        sort: str = "newest",
        limit: int = 20,
        offset: int = 0,
    ) -> list[PublicListingSummary]: ...

    async def count_public(
        self,
        *,
        category: str | None = None,
        q: str | None = None,
        city: str | None = None,
        area: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        seller_handle: str | None = None,
    ) -> int: ...


@runtime_checkable
class FavoriteRepository(Protocol):
    async def add(self, favorite: Favorite) -> Favorite: ...

    async def remove(self, *, user_id: UUID, listing_id: UUID) -> None: ...

    async def exists(self, *, user_id: UUID, listing_id: UUID) -> bool: ...

    async def list_ids_for_user(self, user_id: UUID) -> frozenset[UUID]:
        """Every listing id this user has favorited, unpaginated.

        Used to hydrate a page of catalog cards with "already saved" state
        in one query rather than one per card - a buyer's favorites list is
        small enough that this is cheap.
        """
        ...

    async def list_favorite_listings(
        self, user_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[PublicListingSummary]: ...

    async def count_for_user(self, user_id: UUID) -> int: ...


@runtime_checkable
class ReportRepository(Protocol):
    async def add(self, report: Report) -> Report: ...

    async def get(self, report_id: UUID) -> Report | None: ...

    async def list_for_reporter(self, reporter_id: UUID, *, limit: int = 50) -> list[Report]: ...

    async def list_queue(
        self, *, status: ReportStatus | None = None, limit: int = 50, offset: int = 0
    ) -> list[Report]:
        """The admin work queue - every report, optionally filtered to one
        status, newest first."""
        ...

    async def count_queue(self, *, status: ReportStatus | None = None) -> int: ...

    async def resolve(
        self,
        report_id: UUID,
        *,
        status: ReportStatus,
        resolution_note: str | None,
        resolved_by: UUID,
        resolved_at: datetime,
    ) -> Report: ...


@runtime_checkable
class BlockRepository(Protocol):
    async def add(self, block: Block) -> Block: ...

    async def remove(self, *, blocker_id: UUID, blocked_id: UUID) -> None: ...

    async def exists(self, *, blocker_id: UUID, blocked_id: UUID) -> bool: ...

    async def is_blocked_either_way(self, user_a: UUID, user_b: UUID) -> bool:
        """Messaging enforcement checks both directions - a blocked user
        must not be able to route around a block by starting a fresh
        conversation from the other side."""
        ...

    async def list_blocked_ids(self, blocker_id: UUID) -> frozenset[UUID]: ...


@runtime_checkable
class MessagingRepository(Protocol):
    async def get_conversation(self, conversation_id: UUID) -> Conversation | None: ...

    async def find_conversation(
        self, *, buyer_id: UUID, seller_id: UUID, listing_id: UUID | None
    ) -> Conversation | None:
        """Find-or-create's read half - the same buyer messaging the same
        seller about the same listing lands in one thread, not a new one
        each time."""
        ...

    async def create_conversation(self, conversation: Conversation) -> Conversation: ...

    async def touch_conversation(self, conversation_id: UUID, *, at: datetime) -> None: ...

    async def list_conversations_for_user(
        self, user_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[ConversationSummary]:
        """Every conversation where this user is a participant - as buyer,
        or as the seller (resolved through their seller profile) - ordered
        by most recently active, with unread count and a preview so the
        inbox renders in one round trip."""
        ...

    async def count_conversations_for_user(self, user_id: UUID) -> int: ...

    async def get_participants(self, conversation_id: UUID) -> tuple[UUID, UUID] | None:
        """(buyer_user_id, seller_user_id) for authorization checks - a
        message sender or thread reader must be one of these two."""
        ...

    async def add_message(self, message: Message) -> Message: ...

    async def list_messages(
        self, conversation_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> list[Message]: ...

    async def mark_read(self, conversation_id: UUID, *, reader_id: UUID, at: datetime) -> None:
        """Marks every message in the conversation NOT sent by `reader_id`
        as read - a reader can never mark their own message read."""
        ...


@runtime_checkable
class OfferRepository(Protocol):
    async def add(self, offer: Offer) -> Offer: ...

    async def get(self, offer_id: UUID) -> Offer | None: ...

    async def list_for_conversation(self, conversation_id: UUID) -> list[Offer]:
        """Oldest first - the full negotiation history, offer then
        counter-offer then counter-counter-offer, as it actually happened."""
        ...

    async def get_open_for_listing(self, listing_id: UUID) -> Offer | None:
        """At most one open (PENDING) offer per listing at a time - a second
        offer attempt while one is open should counter it, not race it."""
        ...

    async def close(self, offer_id: UUID, *, status: OfferStatus, responded_at: datetime) -> Offer:
        """Move a PENDING offer to a terminal or counter state. Never used
        to reopen one - status only ever moves forward."""
        ...


@runtime_checkable
class TransactionRepository(Protocol):
    async def add(self, transaction: Transaction) -> Transaction: ...

    async def get(self, transaction_id: UUID) -> Transaction | None: ...

    async def get_open_for_listing(self, listing_id: UUID) -> Transaction | None: ...

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[Transaction]:
        """Every transaction where this user is the buyer or the seller,
        most recent first."""
        ...

    async def update_status(
        self,
        transaction_id: UUID,
        *,
        status: TransactionStatus,
        at: datetime,
        cancel_reason: str | None = None,
    ) -> Transaction: ...


@runtime_checkable
class MeetingVenueRepository(Protocol):
    async def add(self, venue: MeetingVenue) -> MeetingVenue: ...

    async def get(self, venue_id: UUID) -> MeetingVenue | None: ...

    async def list_near(self, *, city: str, limit: int = 5) -> list[MeetingVenue]:
        """Active venues in a city, nearest-first once we have real
        coordinates to sort by - for now, newest-curated first."""
        ...

    async def list_all(self, *, limit: int = 50, offset: int = 0) -> list[MeetingVenue]:
        """The admin management list - active and inactive both."""
        ...

    async def set_active(self, venue_id: UUID, *, is_active: bool) -> MeetingVenue: ...


@runtime_checkable
class MeetupRepository(Protocol):
    async def add(self, meetup: Meetup) -> Meetup: ...

    async def get(self, meetup_id: UUID) -> Meetup | None: ...

    async def list_for_conversation(self, conversation_id: UUID) -> list[Meetup]:
        """Oldest first - every proposal made for this conversation, however
        it was resolved."""
        ...

    async def get_open_for_conversation(self, conversation_id: UUID) -> Meetup | None:
        """At most one open (PROPOSED) meetup per conversation at a time."""
        ...

    async def close(
        self, meetup_id: UUID, *, status: MeetupStatus, responded_at: datetime
    ) -> Meetup: ...


@runtime_checkable
class FollowRepository(Protocol):
    async def add(self, follow: Follow) -> Follow: ...

    async def remove(self, *, follower_id: UUID, seller_id: UUID) -> None: ...

    async def exists(self, *, follower_id: UUID, seller_id: UUID) -> bool: ...

    async def list_followed_seller_ids(self, follower_id: UUID) -> frozenset[UUID]: ...

    async def count_followers(self, seller_id: UUID) -> int: ...


@runtime_checkable
class ReviewRepository(Protocol):
    async def add(self, review: Review) -> Review: ...

    async def get_by_transaction_and_reviewer(
        self, transaction_id: UUID, reviewer_id: UUID
    ) -> Review | None:
        """One review per person per transaction - used both to block a
        duplicate submission and to check whether the counterpart's review
        already exists (the other direction of the same lookup)."""
        ...

    async def list_for_transaction(self, transaction_id: UUID) -> list[Review]: ...

    async def list_visible_for_seller(
        self, seller_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[Review]:
        """Only reviews where the counterpart's review for the same
        transaction also exists - the blind-reveal rule, enforced here
        rather than with a stored flag so there is nothing to keep in sync."""
        ...

    async def get_rating_summary(self, seller_id: UUID) -> SellerRatingSummary: ...


@runtime_checkable
class TrustScoreRepository(Protocol):
    async def get(self, score_id: UUID) -> TrustScore | None: ...

    async def get_current(self, seller_id: UUID) -> TrustScore | None: ...

    async def replace_current(self, score: TrustScore) -> TrustScore:
        """Insert a new score and demote the previous one in one transaction.

        A partial unique index guarantees at most one current score per seller,
        so this invariant is enforced by the database rather than by hope.
        """
        ...

    async def list_history(
        self, seller_id: UUID, *, limit: int = 20, before: datetime | None = None
    ) -> list[TrustScore]: ...


@runtime_checkable
class ScoringModelRepository(Protocol):
    async def get_active(self) -> ScoringModel | None: ...

    async def get(self, model_id: UUID) -> ScoringModel | None: ...

    async def get_by_version(self, version: str) -> ScoringModel | None: ...

    async def list_all(self) -> list[ScoringModel]: ...

    async def list_signal_definitions(self) -> list[SignalDefinition]: ...

    async def create(self, model: ScoringModel) -> ScoringModel: ...

    async def update(self, model: ScoringModel) -> ScoringModel: ...

    async def activate(self, model_id: UUID, *, by: UUID, at: datetime) -> ScoringModel: ...


@runtime_checkable
class AppealRepository(Protocol):
    async def get(self, appeal_id: UUID) -> Appeal | None: ...

    async def add(self, appeal: Appeal) -> Appeal: ...

    async def update(self, appeal: Appeal) -> Appeal: ...

    async def add_message(self, message: AppealMessage) -> AppealMessage: ...

    async def list_for_seller(self, seller_id: UUID) -> list[Appeal]: ...

    async def count_open_for_seller(self, seller_id: UUID) -> int: ...

    async def count_since(self, seller_id: UUID, *, since: datetime) -> int: ...

    async def list_queue(
        self, *, status: AppealStatus | None = None, limit: int = 50, offset: int = 0
    ) -> list[Appeal]: ...


@runtime_checkable
class ReviewCaseRepository(Protocol):
    async def get(self, case_id: UUID) -> ReviewCase | None: ...

    async def add(self, case: ReviewCase) -> ReviewCase: ...

    async def update(self, case: ReviewCase) -> ReviewCase: ...

    async def list_queue(self, *, limit: int = 50, offset: int = 0) -> list[ReviewCase]: ...


@runtime_checkable
class ApiClientRepository(Protocol):
    async def get(self, client_id: UUID) -> ApiClient | None: ...

    async def create(self, client: ApiClient) -> ApiClient: ...

    async def update(self, client: ApiClient) -> ApiClient: ...

    async def list_all(self) -> list[ApiClient]: ...

    async def get_by_slug(self, slug: str) -> ApiClient | None: ...

    async def get_key_by_prefix(self, prefix: str) -> ApiKey | None: ...

    async def get_key(self, key_id: UUID) -> ApiKey | None: ...

    async def list_keys(self, client_id: UUID) -> list[ApiKey]: ...

    async def add_key(self, key: ApiKey) -> ApiKey: ...

    async def revoke_key(self, key_id: UUID, *, by: UUID, at: datetime) -> None: ...

    #: Sets an expiry without revoking, so a rotated key stays usable for the
    #: overlap. Revoking instead would break the partner mid-deploy.
    async def expire_key(self, key_id: UUID, *, at: datetime) -> None: ...

    async def touch_key(self, key_id: UUID, *, at: datetime, ip: str | None) -> None: ...

    async def log_request(self, **kwargs: Any) -> None: ...

    async def usage_this_month(self, client_id: UUID) -> int: ...


@runtime_checkable
class RefreshTokenRepository(Protocol):
    async def get_by_hash(self, token_hash: bytes) -> RefreshToken | None: ...

    async def add(self, token: RefreshToken) -> RefreshToken: ...

    async def revoke(self, token_id: UUID, *, at: datetime, reason: str) -> None: ...

    async def revoke_family(self, family_id: UUID, *, at: datetime, reason: str) -> int:
        """Reuse detection: kill every descendant of a stolen token."""
        ...

    async def revoke_all_for_user(
        self, user_id: UUID, *, at: datetime, reason: str, except_id: UUID | None = None
    ) -> int: ...

    async def list_active_for_user(self, user_id: UUID) -> list[RefreshToken]: ...

    async def delete_expired(self, *, before: datetime) -> int: ...


@runtime_checkable
class VerificationTokenRepository(Protocol):
    async def get_by_hash(
        self, token_hash: bytes, *, purpose: TokenPurpose
    ) -> VerificationToken | None: ...

    async def add(self, token: VerificationToken) -> VerificationToken: ...

    async def consume(self, token_id: UUID, *, at: datetime) -> None: ...

    async def invalidate_for_user(self, user_id: UUID, *, purpose: TokenPurpose) -> int: ...


@runtime_checkable
class MfaRecoveryCodeRepository(Protocol):
    """One-time backup codes for staff MFA (BLK-04) - issued as a set of 10
    whenever enrollment is confirmed (replacing any previous set), each
    usable exactly once if a TOTP device is lost. Hashed with the same
    peppered `TokenHasher` refresh/verification tokens use, not argon2:
    these are high-entropy random strings, not user-chosen passwords, so a
    fast deterministic hash (letting lookup-by-hash work at all) loses
    nothing a slow one would have bought."""

    async def replace_all(
        self, user_id: UUID, code_hashes: list[bytes], *, created_at: datetime
    ) -> None: ...

    async def get_unused_by_hash(self, user_id: UUID, code_hash: bytes) -> UUID | None:
        """The matching row's id, so the caller can `consume` it - or None
        if no unused code hashes to this value."""
        ...

    async def consume(self, code_id: UUID, *, at: datetime) -> None: ...

    async def count_unused(self, user_id: UUID) -> int: ...


@runtime_checkable
class OtpRepository(Protocol):
    async def get_active(self, user_id: UUID, *, purpose: OtpPurpose) -> OtpCode | None: ...

    async def add(self, otp: OtpCode) -> OtpCode: ...

    async def increment_attempts(self, otp_id: UUID) -> int:
        """Atomic increment. A read-modify-write here would let concurrent
        requests brute-force past the attempt cap."""
        ...

    async def consume(self, otp_id: UUID, *, at: datetime) -> None: ...

    async def count_sent_since(self, user_id: UUID, *, since: datetime) -> int: ...


@runtime_checkable
class ConsentRepository(Protocol):
    async def has_granted(self, user_id: UUID, *, consent_type: str) -> bool: ...

    async def record(self, consent: Consent) -> Consent: ...

    async def list_for_user(self, user_id: UUID) -> list[Consent]: ...


@runtime_checkable
class FileRepository(Protocol):
    async def get(self, file_id: UUID) -> StoredFile | None: ...

    async def add(self, file: StoredFile) -> StoredFile: ...

    async def update(self, file: StoredFile) -> StoredFile: ...

    async def list_expired(self, *, before: datetime, limit: int) -> list[StoredFile]: ...

    async def mark_deleted(self, file_id: UUID, *, at: datetime) -> None: ...


@runtime_checkable
class NotificationRepository(Protocol):
    async def add(self, notification: Notification) -> Notification: ...

    async def list_for_user(
        self, user_id: UUID, *, unread_only: bool = False, limit: int = 50
    ) -> list[Notification]: ...

    async def mark_read(self, notification_id: UUID, *, at: datetime) -> None: ...

    async def mark_all_read(self, user_id: UUID, *, at: datetime) -> int: ...


@runtime_checkable
class AuditLogRepository(Protocol):
    async def record(self, entry: AuditLogEntry) -> None: ...

    async def list_for_entity(
        self, *, entity_type: str, entity_id: UUID, limit: int = 50
    ) -> list[AuditLogEntry]: ...

    async def search(self, **filters: Any) -> list[AuditLogEntry]: ...


@runtime_checkable
class JobRunRepository(Protocol):
    async def get(self, job_id: UUID) -> JobRun | None: ...

    async def get_by_key(self, job_key: str) -> JobRun | None: ...

    async def add(self, job: JobRun) -> JobRun: ...

    async def update(self, job: JobRun) -> JobRun: ...

    async def list_dead_letters(self, *, limit: int = 50) -> list[JobRun]: ...


__all__ = [
    "ApiClientRepository",
    "AppealRepository",
    "AuditLogRepository",
    "ConsentRepository",
    "DeviceRepository",
    "EmailAddressRepository",
    "FavoriteRepository",
    "FileRepository",
    "IdentityRepository",
    "JobRunRepository",
    "ListingRepository",
    "MessagingRepository",
    "NotificationRepository",
    "OtpRepository",
    "PhoneNumberRepository",
    "RefreshTokenRepository",
    "ReviewCaseRepository",
    "ScoringModelRepository",
    "SellerRepository",
    "TrustScoreRepository",
    "UserRepository",
    "VerificationTokenRepository",
]
