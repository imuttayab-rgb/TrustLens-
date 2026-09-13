"""Domain enumerations.

Every value here has a matching PostgreSQL ENUM type (see database/migrations).
Adding a member therefore requires a migration - which is the point: an
unmigrated enum value would fail at insert time in production rather than at
review time.
"""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    BUYER = "BUYER"
    SELLER = "SELLER"
    REVIEWER = "REVIEWER"
    ADMIN = "ADMIN"


class AccountStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    BANNED = "BANNED"
    DELETED = "DELETED"


class VerificationStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"

    @property
    def is_terminal(self) -> bool:
        return self in {
            VerificationStatus.VERIFIED,
            VerificationStatus.REJECTED,
            VerificationStatus.EXPIRED,
            VerificationStatus.FAILED,
        }


class DocumentType(StrEnum):
    CNIC_FRONT = "CNIC_FRONT"
    CNIC_BACK = "CNIC_BACK"
    SELFIE = "SELFIE"
    PASSPORT = "PASSPORT"
    OTHER = "OTHER"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    #: Not enough evidence to judge. A brand-new honest seller and a proven
    #: scammer must never render identically - see docs/08 section 4.
    UNKNOWN = "UNKNOWN"


class SignalCategory(StrEnum):
    IDENTITY = "IDENTITY"
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    DEVICE = "DEVICE"
    NETWORK = "NETWORK"
    BEHAVIOUR = "BEHAVIOUR"
    LISTING = "LISTING"


class SignalStatus(StrEnum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"
    #: The check could not run (provider outage, timeout). Excluded from the
    #: denominator so our outage never penalises a seller.
    UNAVAILABLE = "UNAVAILABLE"
    #: The check does not apply (e.g. no listings yet). Also excluded.
    NOT_APPLICABLE = "NOT_APPLICABLE"

    @property
    def counts_toward_evidence(self) -> bool:
        return self in {SignalStatus.PASS, SignalStatus.PARTIAL, SignalStatus.FAIL}


class SignalCode(StrEnum):
    """The v1 signal catalogue. Mirrors the `signal_definitions` seed rows."""

    IDENTITY_DOCUMENT_VALID = "IDENTITY_DOCUMENT_VALID"
    IDENTITY_FACE_MATCH = "IDENTITY_FACE_MATCH"
    PHONE_VERIFIED = "PHONE_VERIFIED"
    PHONE_NOT_DISPOSABLE = "PHONE_NOT_DISPOSABLE"
    EMAIL_VERIFIED = "EMAIL_VERIFIED"
    EMAIL_NOT_DISPOSABLE = "EMAIL_NOT_DISPOSABLE"
    DEVICE_NOT_SHARED = "DEVICE_NOT_SHARED"
    DEVICE_CONSISTENT = "DEVICE_CONSISTENT"
    NETWORK_NOT_VPN = "NETWORK_NOT_VPN"
    NETWORK_GEO_CONSISTENT = "NETWORK_GEO_CONSISTENT"
    ACCOUNT_AGE = "ACCOUNT_AGE"
    ACTIVITY_CONSISTENT = "ACTIVITY_CONSISTENT"
    LISTING_CONTENT_SAFE = "LISTING_CONTENT_SAFE"
    LISTING_PRICE_REALISTIC = "LISTING_PRICE_REALISTIC"


class ReasonCode(StrEnum):
    """Stable, machine-readable explanations.

    Clients switch on these; they are localisable and must never be reworded
    in place - a changed meaning requires a new code.
    """

    IDENTITY_VERIFIED = "IDENTITY_VERIFIED"
    IDENTITY_NOT_SUBMITTED = "IDENTITY_NOT_SUBMITTED"
    IDENTITY_PENDING_REVIEW = "IDENTITY_PENDING_REVIEW"
    FACE_MATCH_HIGH = "FACE_MATCH_HIGH"
    FACE_MATCH_BORDERLINE = "FACE_MATCH_BORDERLINE"
    FACE_MATCH_LOW = "FACE_MATCH_LOW"
    CNIC_EXPIRED = "CNIC_EXPIRED"
    CNIC_UNREADABLE = "CNIC_UNREADABLE"
    CNIC_DUPLICATE = "CNIC_DUPLICATE"
    PHONE_VERIFIED_OK = "PHONE_VERIFIED_OK"
    PHONE_NOT_VERIFIED = "PHONE_NOT_VERIFIED"
    PHONE_LINE_TYPE_VOIP = "PHONE_LINE_TYPE_VOIP"
    PHONE_REUSED = "PHONE_REUSED"
    EMAIL_VERIFIED_OK = "EMAIL_VERIFIED_OK"
    EMAIL_NOT_VERIFIED = "EMAIL_NOT_VERIFIED"
    EMAIL_DOMAIN_DISPOSABLE = "EMAIL_DOMAIN_DISPOSABLE"
    EMAIL_DOMAIN_NEW = "EMAIL_DOMAIN_NEW"
    DEVICE_CLEAN = "DEVICE_CLEAN"
    DEVICE_SHARED_MANY_ACCOUNTS = "DEVICE_SHARED_MANY_ACCOUNTS"
    DEVICE_EMULATOR = "DEVICE_EMULATOR"
    NETWORK_CLEAN = "NETWORK_CLEAN"
    NETWORK_VPN_DETECTED = "NETWORK_VPN_DETECTED"
    NETWORK_DATACENTER_IP = "NETWORK_DATACENTER_IP"
    GEO_MISMATCH = "GEO_MISMATCH"
    ACCOUNT_ESTABLISHED = "ACCOUNT_ESTABLISHED"
    ACCOUNT_TOO_NEW = "ACCOUNT_TOO_NEW"
    ACTIVITY_NORMAL = "ACTIVITY_NORMAL"
    ACTIVITY_IRREGULAR = "ACTIVITY_IRREGULAR"
    LISTINGS_CLEAN = "LISTINGS_CLEAN"
    LISTING_URGENCY_PRESSURE = "LISTING_URGENCY_PRESSURE"
    LISTING_OFF_PLATFORM_CONTACT = "LISTING_OFF_PLATFORM_CONTACT"
    LISTING_SCAM_PATTERN = "LISTING_SCAM_PATTERN"
    PRICE_REALISTIC = "PRICE_REALISTIC"
    PRICE_TOO_GOOD_TO_BE_TRUE = "PRICE_TOO_GOOD_TO_BE_TRUE"
    NO_LISTINGS = "NO_LISTINGS"
    SIGNAL_UNAVAILABLE = "SIGNAL_UNAVAILABLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    ADMIN_OVERRIDE = "ADMIN_OVERRIDE"
    ADMIN_FLAGGED = "ADMIN_FLAGGED"


class ScoreTrigger(StrEnum):
    SIGNAL_CHANGE = "SIGNAL_CHANGE"
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"
    MODEL_CHANGE = "MODEL_CHANGE"
    API_REQUEST = "API_REQUEST"
    APPEAL_RESOLUTION = "APPEAL_RESOLUTION"


class ListingStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ANALYSING = "ANALYSING"
    FLAGGED = "FLAGGED"
    REMOVED = "REMOVED"
    EXPIRED = "EXPIRED"


class ListingSource(StrEnum):
    MANUAL = "MANUAL"
    URL_IMPORT = "URL_IMPORT"
    API = "API"


class AppealStatus(StrEnum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    NEEDS_INFO = "NEEDS_INFO"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"

    @property
    def is_open(self) -> bool:
        return self in {AppealStatus.OPEN, AppealStatus.UNDER_REVIEW, AppealStatus.NEEDS_INFO}


class ReviewStatus(StrEnum):
    QUEUED = "QUEUED"
    ASSIGNED = "ASSIGNED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"


class ReviewCaseType(StrEnum):
    IDENTITY_REVIEW = "IDENTITY_REVIEW"
    FRAUD_FLAG = "FRAUD_FLAG"
    APPEAL = "APPEAL"
    DEVICE_CLUSTER = "DEVICE_CLUSTER"


class ReportTargetType(StrEnum):
    LISTING = "LISTING"
    SELLER = "SELLER"
    MESSAGE = "MESSAGE"
    OTHER = "OTHER"


class ReportCategory(StrEnum):
    SCAM_OR_FRAUD = "SCAM_OR_FRAUD"
    PROHIBITED_ITEM = "PROHIBITED_ITEM"
    HARASSMENT = "HARASSMENT"
    MISLEADING_LISTING = "MISLEADING_LISTING"
    OTHER = "OTHER"


class ReportStatus(StrEnum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"

    @property
    def is_open(self) -> bool:
        return self in {ReportStatus.OPEN, ReportStatus.UNDER_REVIEW}


class ApiKeyStatus(StrEnum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    DEAD = "DEAD"

    @property
    def is_terminal(self) -> bool:
        return self in {
            JobStatus.SUCCEEDED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
            JobStatus.DEAD,
        }


class FilePurpose(StrEnum):
    CNIC_FRONT = "CNIC_FRONT"
    CNIC_BACK = "CNIC_BACK"
    SELFIE = "SELFIE"
    LISTING_IMAGE = "LISTING_IMAGE"
    APPEAL_EVIDENCE = "APPEAL_EVIDENCE"
    MODEL_ARTIFACT = "MODEL_ARTIFACT"

    @property
    def is_sensitive(self) -> bool:
        """Sensitive purposes go to the private documents bucket and are purged
        after MEDIA_RETENTION_DAYS_IDENTITY."""
        return self in {FilePurpose.CNIC_FRONT, FilePurpose.CNIC_BACK, FilePurpose.SELFIE}


class ScanStatus(StrEnum):
    PENDING = "PENDING"
    CLEAN = "CLEAN"
    INFECTED = "INFECTED"
    SKIPPED = "SKIPPED"


class ConsentType(StrEnum):
    TERMS = "TERMS"
    PRIVACY = "PRIVACY"
    BIOMETRIC_PROCESSING = "BIOMETRIC_PROCESSING"
    DATA_SHARING = "DATA_SHARING"


class OtpPurpose(StrEnum):
    PHONE_VERIFICATION = "PHONE_VERIFICATION"
    LOGIN_MFA = "LOGIN_MFA"
    PHONE_CHANGE = "PHONE_CHANGE"


class TokenPurpose(StrEnum):
    EMAIL_VERIFICATION = "EMAIL_VERIFICATION"
    PASSWORD_RESET = "PASSWORD_RESET"
    EMAIL_CHANGE = "EMAIL_CHANGE"


class LineType(StrEnum):
    MOBILE = "MOBILE"
    VOIP = "VOIP"
    LANDLINE = "LANDLINE"
    UNKNOWN = "UNKNOWN"


class ActorType(StrEnum):
    USER = "USER"
    SYSTEM = "SYSTEM"
    API_CLIENT = "API_CLIENT"


class WebhookEvent(StrEnum):
    SCORE_UPDATED = "SCORE_UPDATED"
    SELLER_VERIFIED = "SELLER_VERIFIED"
    SELLER_FLAGGED = "SELLER_FLAGGED"
    APPEAL_RESOLVED = "APPEAL_RESOLVED"


class DeliveryStatus(StrEnum):
    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    EXHAUSTED = "EXHAUSTED"


__all__ = [
    "AccountStatus",
    "ActorType",
    "ApiKeyStatus",
    "AppealStatus",
    "ConsentType",
    "DeliveryStatus",
    "DocumentType",
    "FilePurpose",
    "JobStatus",
    "LineType",
    "ListingSource",
    "ListingStatus",
    "OtpPurpose",
    "ReasonCode",
    "ReportCategory",
    "ReportStatus",
    "ReportTargetType",
    "ReviewCaseType",
    "ReviewStatus",
    "RiskLevel",
    "ScanStatus",
    "ScoreTrigger",
    "SignalCategory",
    "SignalCode",
    "SignalStatus",
    "TokenPurpose",
    "UserRole",
    "VerificationStatus",
    "WebhookEvent",
]
