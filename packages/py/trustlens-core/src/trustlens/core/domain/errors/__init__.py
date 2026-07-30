"""Domain errors.

Every error carries a stable machine-readable `code`. Clients switch on the
code, never on the message - messages are localisable prose, codes are API.

The HTTP mapping lives in apps/api/exceptions/mapping.py so the domain stays
transport-agnostic.
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base class for every expected failure in the domain."""

    code: str = "DOMAIN_ERROR"
    title: str = "Domain error"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.title
        self.details = details or {}
        super().__init__(self.message)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


# ── Generic ──────────────────────────────────────────────────────────


class ValidationError(DomainError):
    code = "VALIDATION_FAILED"
    title = "Validation failed"

    def __init__(
        self, message: str, *, field: str | None = None, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message, details=details)
        self.field = field


class EntityNotFound(DomainError):
    code = "NOT_FOUND"
    title = "Resource not found"

    def __init__(self, entity: str, identifier: Any = None) -> None:
        super().__init__(
            f"{entity} not found", details={"entity": entity, "id": str(identifier or "")}
        )
        self.entity = entity


class ConflictError(DomainError):
    code = "CONFLICT"
    title = "Conflict"


class VersionConflict(ConflictError):
    """Optimistic locking failure - someone else edited this row first."""

    code = "VERSION_CONFLICT"
    title = "The resource was modified by someone else"


class InvalidStateError(DomainError):
    """The operation is valid in general, but not for this entity right now."""

    code = "INVALID_STATE"
    title = "Operation not allowed in the current state"


class RateLimitExceeded(DomainError):
    code = "RATE_LIMITED"
    title = "Too many requests"

    def __init__(self, message: str = "Too many requests", *, retry_after: int = 60) -> None:
        super().__init__(message, details={"retry_after": retry_after})
        self.retry_after = retry_after


class ExternalServiceError(DomainError):
    """An upstream dependency failed. Distinct from our own bugs, because it
    drives a retry rather than a 500."""

    code = "UPSTREAM_FAILED"
    title = "An upstream service failed"

    def __init__(self, service: str, message: str | None = None) -> None:
        super().__init__(message or f"{service} is unavailable", details={"service": service})
        self.service = service


# ── Authentication and authorization ─────────────────────────────────


class AuthenticationError(DomainError):
    code = "UNAUTHENTICATED"
    title = "Authentication required"


class InvalidCredentials(AuthenticationError):
    code = "INVALID_CREDENTIALS"
    title = "Invalid email or password"

    def __init__(self) -> None:
        # Deliberately identical whether the account exists or not: a distinct
        # message would make the endpoint a user-enumeration oracle.
        super().__init__("Invalid email or password")


class AccountNotActive(AuthenticationError):
    code = "ACCOUNT_NOT_ACTIVE"
    title = "Account is not active"


class AccountLocked(AuthenticationError):
    code = "ACCOUNT_LOCKED"
    title = "Account temporarily locked"

    def __init__(self, retry_after: int) -> None:
        super().__init__(
            "Too many failed attempts. Try again later.", details={"retry_after": retry_after}
        )
        self.retry_after = retry_after


class EmailNotVerified(AuthenticationError):
    code = "EMAIL_NOT_VERIFIED"
    title = "Email address is not verified"


class TokenInvalid(AuthenticationError):
    code = "TOKEN_INVALID"
    title = "Token is invalid or expired"


class TokenReuseDetected(AuthenticationError):
    """A rotated refresh token was presented again.

    Treated as theft: the whole token family is revoked. See ADR-0006.
    """

    code = "TOKEN_REUSE_DETECTED"
    title = "Session revoked for security reasons"

    def __init__(self) -> None:
        super().__init__(
            "This session was revoked because a previously used token was presented again. "
            "Please sign in again."
        )


class MfaRequired(AuthenticationError):
    code = "MFA_REQUIRED"
    title = "Multi-factor authentication required"


class PermissionDenied(DomainError):
    code = "PERMISSION_DENIED"
    title = "You do not have permission to perform this action"

    def __init__(self, permission: str | None = None) -> None:
        super().__init__(
            "You do not have permission to perform this action",
            details={"required_permission": permission} if permission else {},
        )


# ── Verification ─────────────────────────────────────────────────────


class VerificationError(DomainError):
    code = "VERIFICATION_FAILED"
    title = "Verification failed"


class OtpExpired(VerificationError):
    code = "OTP_EXPIRED"
    title = "The code has expired"


class OtpInvalid(VerificationError):
    code = "OTP_INVALID"
    title = "The code is incorrect"


class OtpMaxAttemptsExceeded(VerificationError):
    code = "OTP_MAX_ATTEMPTS"
    title = "Too many incorrect attempts"


class DocumentUnreadable(VerificationError):
    code = "DOCUMENT_UNREADABLE"
    title = "The document could not be read"


class DocumentExpired(VerificationError):
    code = "DOCUMENT_EXPIRED"
    title = "The submitted document has expired"


class FaceMatchFailed(VerificationError):
    code = "FACE_MATCH_FAILED"
    title = "The selfie does not match the document photo"


class DuplicateIdentity(VerificationError):
    code = "DUPLICATE_IDENTITY"
    title = "This identity document is already registered to another account"


class ConsentRequired(VerificationError):
    code = "CONSENT_REQUIRED"
    title = "Consent is required before this data can be processed"

    def __init__(self, consent_type: str) -> None:
        super().__init__(
            f"{consent_type} consent is required before continuing",
            details={"consent_type": consent_type},
        )


class UnsupportedFileType(ValidationError):
    code = "UNSUPPORTED_FILE_TYPE"
    title = "Unsupported file type"


class FileTooLarge(ValidationError):
    code = "FILE_TOO_LARGE"
    title = "File is too large"


# ── Scoring ──────────────────────────────────────────────────────────


class ScoringError(DomainError):
    code = "SCORING_FAILED"
    title = "Trust score could not be computed"


class NoActiveScoringModel(ScoringError):
    code = "NO_ACTIVE_SCORING_MODEL"
    title = "No active scoring model is configured"


class InvalidScoringModel(ScoringError):
    code = "INVALID_SCORING_MODEL"
    title = "The scoring model configuration is invalid"


class OverrideReasonRequired(ValidationError):
    code = "OVERRIDE_REASON_REQUIRED"
    title = "A reason is required to override a trust score"

    def __init__(self) -> None:
        super().__init__(
            "A written reason is required when overriding a computed score", field="reason"
        )


# ── Appeals ──────────────────────────────────────────────────────────


class AppealNotAllowed(InvalidStateError):
    code = "APPEAL_NOT_ALLOWED"
    title = "This score cannot be appealed"


class AppealLimitReached(RateLimitExceeded):
    code = "APPEAL_LIMIT_REACHED"
    title = "Appeal limit reached"


# ── Public API ───────────────────────────────────────────────────────


class ApiKeyInvalid(AuthenticationError):
    code = "API_KEY_INVALID"
    title = "Invalid API key"


class ApiKeyRevoked(AuthenticationError):
    code = "API_KEY_REVOKED"
    title = "This API key has been revoked"


class ApiScopeMissing(PermissionDenied):
    code = "API_SCOPE_MISSING"
    title = "The API key lacks the required scope"


class QuotaExceeded(RateLimitExceeded):
    code = "QUOTA_EXCEEDED"
    title = "Monthly quota exceeded"


class IdempotencyKeyReused(ConflictError):
    code = "IDEMPOTENCY_KEY_REUSED"
    title = "This idempotency key was used with a different request body"


__all__ = [
    "AccountLocked",
    "AccountNotActive",
    "ApiKeyInvalid",
    "ApiKeyRevoked",
    "ApiScopeMissing",
    "AppealLimitReached",
    "AppealNotAllowed",
    "AuthenticationError",
    "ConflictError",
    "ConsentRequired",
    "DocumentExpired",
    "DocumentUnreadable",
    "DomainError",
    "DuplicateIdentity",
    "EmailNotVerified",
    "EntityNotFound",
    "ExternalServiceError",
    "FaceMatchFailed",
    "FileTooLarge",
    "IdempotencyKeyReused",
    "InvalidCredentials",
    "InvalidScoringModel",
    "InvalidStateError",
    "MfaRequired",
    "NoActiveScoringModel",
    "OtpExpired",
    "OtpInvalid",
    "OtpMaxAttemptsExceeded",
    "OverrideReasonRequired",
    "PermissionDenied",
    "QuotaExceeded",
    "RateLimitExceeded",
    "ScoringError",
    "TokenInvalid",
    "TokenReuseDetected",
    "UnsupportedFileType",
    "ValidationError",
    "VerificationError",
    "VersionConflict",
]
