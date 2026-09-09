"""Ports - the seams of the system.

These are `Protocol` interfaces, not ABCs: adapters implement them
structurally, with no inheritance link back into the domain. That keeps the
dependency arrow pointing inward (ADR-0004) and lets a test fake satisfy the
same contract as a production adapter without importing anything from it.

Every port is narrow on purpose (interface segregation): `OcrEngine` has one
method rather than being folded into an `AiService` god-object, so a fake for
one capability does not have to stub five others.
"""

from __future__ import annotations

from trustlens.core.domain.ports.ai import (
    ClassifierResult,
    FaceMatcher,
    FaceMatchResult,
    ListingAnalysisResult,
    LlmAnalyzer,
    OcrEngine,
    OcrResult,
    ScamClassifier,
)
from trustlens.core.domain.ports.infrastructure import (
    ApiKeyGenerator,
    Cache,
    Clock,
    EmailSender,
    IdGenerator,
    IpIntelligence,
    JobQueue,
    ObjectStorage,
    PhoneLookup,
    PresignedUpload,
    ResponseSigner,
    SmsSender,
    UnitOfWork,
)
from trustlens.core.domain.ports.repositories import (
    ApiClientRepository,
    AppealRepository,
    AuditLogRepository,
    ConsentRepository,
    DeviceRepository,
    EmailAddressRepository,
    FavoriteRepository,
    FileRepository,
    IdentityRepository,
    JobRunRepository,
    ListingRepository,
    NotificationRepository,
    OtpRepository,
    PhoneNumberRepository,
    RefreshTokenRepository,
    ReviewCaseRepository,
    ScoringModelRepository,
    SellerRepository,
    TrustScoreRepository,
    UserRepository,
    VerificationTokenRepository,
)

__all__ = [
    "ApiClientRepository",
    "ApiKeyGenerator",
    "AppealRepository",
    "AuditLogRepository",
    "Cache",
    "ClassifierResult",
    "Clock",
    "ConsentRepository",
    "DeviceRepository",
    "EmailAddressRepository",
    "EmailSender",
    "FaceMatchResult",
    "FaceMatcher",
    "FavoriteRepository",
    "FileRepository",
    "IdGenerator",
    "IdentityRepository",
    "IpIntelligence",
    "JobQueue",
    "JobRunRepository",
    "ListingAnalysisResult",
    "ListingRepository",
    "LlmAnalyzer",
    "NotificationRepository",
    "ObjectStorage",
    "OcrEngine",
    "OcrResult",
    "OtpRepository",
    "PhoneLookup",
    "PhoneNumberRepository",
    "PresignedUpload",
    "RefreshTokenRepository",
    "ResponseSigner",
    "ReviewCaseRepository",
    "ScamClassifier",
    "ScoringModelRepository",
    "SellerRepository",
    "SmsSender",
    "TrustScoreRepository",
    "UnitOfWork",
    "UserRepository",
    "VerificationTokenRepository",
]
