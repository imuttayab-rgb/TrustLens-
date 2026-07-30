"""Verification evidence entities: identity, contact, device and network.

These hold the *raw evidence* behind signals 1-6. The scoring engine never
reads them directly - signal collectors turn them into `SignalEvaluation`
objects, which is the boundary that keeps scoring logic independent of how
any particular check happens to be implemented.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from uuid import UUID

from trustlens.core.domain.enums import (
    DocumentType,
    FilePurpose,
    LineType,
    ScanStatus,
    VerificationStatus,
)
from trustlens.core.domain.value_objects import Email, PhoneE164


@dataclass(frozen=True, slots=True)
class StoredFile:
    """A binary in object storage.

    Every upload lands here so the retention job has exactly one place to look
    - a hard requirement given CNIC images must be purged after 90 days.
    """

    id: UUID
    purpose: FilePurpose
    bucket: str
    object_key: str
    mime_type: str
    size_bytes: int
    sha256: bytes
    created_at: datetime
    owner_user_id: UUID | None = None
    original_filename: str | None = None
    width: int | None = None
    height: int | None = None
    scan_status: ScanStatus = ScanStatus.PENDING
    is_encrypted: bool = True
    expires_at: datetime | None = None
    deleted_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class OcrFields:
    """Fields extracted from a CNIC by OCR, before the seller confirms them."""

    full_name: str | None = None
    cnic_number: str | None = None
    date_of_birth: date | None = None
    expiry_date: date | None = None
    father_name: str | None = None
    address: str | None = None


@dataclass(frozen=True, slots=True)
class IdentityDocument:
    """One submitted document plus its OCR result.

    `extracted_cnic_hash` is an HMAC, not the number: it enables
    duplicate-CNIC detection (one ID across many accounts - the classic
    multi-account fraud pattern) with the number itself encrypted at rest.
    """

    id: UUID
    seller_id: UUID
    document_type: DocumentType
    file_id: UUID
    status: VerificationStatus
    created_at: datetime
    ocr_engine: str | None = None
    ocr_engine_version: str | None = None
    ocr_confidence: float | None = None
    ocr_raw: dict[str, Any] = field(default_factory=dict)
    fields: OcrFields = field(default_factory=OcrFields)
    extracted_cnic_hash: bytes | None = None
    quality_score: float | None = None
    rejection_reason: str | None = None
    processed_at: datetime | None = None

    def is_expired_on(self, today: date) -> bool:
        return self.fields.expiry_date is not None and self.fields.expiry_date < today


@dataclass(frozen=True, slots=True)
class IdentityVerification:
    """The face-match decision.

    `threshold_used` is stored alongside `face_similarity` deliberately:
    without it, a past rejection becomes indefensible once the threshold is
    retuned, and an appeal cannot be adjudicated.
    """

    id: UUID
    seller_id: UUID
    decision: VerificationStatus
    created_at: datetime
    front_document_id: UUID | None = None
    back_document_id: UUID | None = None
    selfie_document_id: UUID | None = None
    face_match_engine: str | None = None
    engine_version: str | None = None
    face_similarity: float | None = None
    face_distance: float | None = None
    threshold_used: float | None = None
    liveness_passed: bool | None = None
    name_match_score: float | None = None
    decision_source: str = "AUTO"
    decided_by: UUID | None = None
    decision_reason: str | None = None
    raw_result: dict[str, Any] = field(default_factory=dict)
    verified_at: datetime | None = None

    @property
    def is_verified(self) -> bool:
        return self.decision == VerificationStatus.VERIFIED


@dataclass(frozen=True, slots=True)
class PhoneNumber:
    """A seller phone number and what we know about it.

    `line_type == VOIP` is precisely the "throwaway phone number" pattern the
    proposal names in its problem statement.
    """

    id: UUID
    user_id: UUID
    e164: PhoneE164
    created_at: datetime
    is_primary: bool = True
    verified_at: datetime | None = None
    carrier_name: str | None = None
    line_type: LineType = LineType.UNKNOWN
    is_disposable: bool = False
    country_code: str | None = None
    lookup_raw: dict[str, Any] = field(default_factory=dict)
    lookup_at: datetime | None = None
    deleted_at: datetime | None = None

    @property
    def is_verified(self) -> bool:
        return self.verified_at is not None


@dataclass(frozen=True, slots=True)
class EmailAddress:
    """A seller email address and its check results.

    Separate from `users.email` because a seller may add a business address,
    and because email checks produce evidence that must be re-runnable
    independently of the login credential.
    """

    id: UUID
    user_id: UUID
    email: Email
    created_at: datetime
    is_primary: bool = True
    verified_at: datetime | None = None
    is_disposable: bool = False
    mx_valid: bool | None = None
    domain_age_days: int | None = None
    lookup_raw: dict[str, Any] = field(default_factory=dict)
    lookup_at: datetime | None = None
    deleted_at: datetime | None = None

    @property
    def is_verified(self) -> bool:
        return self.verified_at is not None

    @property
    def domain(self) -> str:
        return self.email.domain


@dataclass(frozen=True, slots=True)
class Device:
    id: UUID
    fingerprint_hash: bytes
    first_seen_at: datetime
    last_seen_at: datetime
    user_agent: str | None = None
    browser: str | None = None
    os: str | None = None
    device_type: str | None = None
    screen_resolution: str | None = None
    timezone: str | None = None
    is_bot: bool = False
    is_emulator: bool = False


@dataclass(frozen=True, slots=True)
class DeviceLink:
    """A user<->device association. The many-to-many is the whole point: it is
    how "multiple accounts created from one device" is detected."""

    user_id: UUID
    device_id: UUID
    first_seen_at: datetime
    last_seen_at: datetime
    session_count: int = 1
    is_trusted: bool = False


@dataclass(frozen=True, slots=True)
class IpReputation:
    """What an IP-intelligence provider says about an address.

    One row per distinct IP so a metered lookup happens once, not per request.
    """

    ip: str
    country_code: str | None = None
    region: str | None = None
    city: str | None = None
    asn: int | None = None
    asn_org: str | None = None
    is_vpn: bool = False
    is_proxy: bool = False
    is_tor: bool = False
    is_datacenter: bool = False
    abuse_score: int = 0
    provider: str = "offline"
    looked_up_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_anonymised(self) -> bool:
        return self.is_vpn or self.is_proxy or self.is_tor or self.is_datacenter


@dataclass(frozen=True, slots=True)
class AccessEvent:
    """Append-only record of an authenticated interaction.

    Feeds both the NETWORK signal and the BEHAVIOUR (activity) signal, and is
    the forensic trail when a fraud pattern has to be reconstructed.
    """

    id: UUID
    event_type: str
    occurred_at: datetime
    user_id: UUID | None = None
    device_id: UUID | None = None
    ip_address_id: UUID | None = None
    ip: str | None = None
    request_id: str | None = None
    user_agent: str | None = None


__all__ = [
    "AccessEvent",
    "Device",
    "DeviceLink",
    "EmailAddress",
    "IdentityDocument",
    "IdentityVerification",
    "IpReputation",
    "OcrFields",
    "PhoneNumber",
    "StoredFile",
]
