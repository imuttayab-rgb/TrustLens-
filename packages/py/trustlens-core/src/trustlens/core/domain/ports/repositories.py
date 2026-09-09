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
        Consent,
        Device,
        DeviceLink,
        EmailAddress,
        Favorite,
        IdentityDocument,
        IdentityVerification,
        IpReputation,
        JobRun,
        Listing,
        ListingAnalysis,
        Notification,
        OtpCode,
        PhoneNumber,
        PublicListingSummary,
        RefreshToken,
        ReviewCase,
        ScoringModel,
        SellerProfile,
        SignalDefinition,
        StoredFile,
        TrustScore,
        User,
        VerificationToken,
    )
    from trustlens.core.domain.enums import AppealStatus, OtpPurpose, TokenPurpose
    from trustlens.core.domain.value_objects import Email, PhoneE164


@runtime_checkable
class UserRepository(Protocol):
    async def get(self, user_id: UUID) -> User | None: ...

    async def get_by_email(self, email: Email) -> User | None: ...

    async def get_password_hash(self, user_id: UUID) -> str | None: ...

    async def create(self, *, user: User, password_hash: str | None) -> User: ...

    async def update(self, user: User) -> User: ...

    async def set_password_hash(self, user_id: UUID, password_hash: str) -> None: ...

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

    async def search_public(
        self,
        *,
        category: str | None = None,
        q: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[PublicListingSummary]: ...

    async def count_public(self, *, category: str | None = None, q: str | None = None) -> int: ...


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
