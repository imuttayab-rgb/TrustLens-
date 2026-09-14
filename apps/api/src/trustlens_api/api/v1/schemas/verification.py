"""Verification schemas (features F1-F4)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from trustlens_api.api.v1.schemas.common import Schema


class UploadIntentRequest(Schema):
    purpose: str = Field(
        description="CNIC_FRONT | CNIC_BACK | SELFIE | LISTING_IMAGE | LISTING_VIDEO"
    )
    content_type: str
    size_bytes: int = Field(gt=0)
    filename: str | None = Field(default=None, max_length=255)

    @field_validator("content_type")
    @classmethod
    def _allowed(cls, v: str) -> str:
        # Advisory only. The real check (including the actual per-purpose
        # size/mime limits) happens in the handler, which knows the
        # purpose; this is just a first, purpose-blind filter against
        # anything that couldn't ever be a valid upload.
        if v not in {"image/jpeg", "image/png", "image/webp", "video/mp4"}:
            raise ValueError("Only JPEG, PNG, WEBP images or an MP4 video are accepted.")
        return v


class UploadIntentResponse(Schema):
    file_id: UUID
    upload_url: str
    fields: dict[str, str]
    expires_at: datetime
    max_bytes: int


class SubmitIdentityRequest(Schema):
    cnic_front_file_id: UUID
    cnic_back_file_id: UUID
    selfie_file_id: UUID
    #: Biometric processing requires explicit, versioned consent before the
    #: face comparison may run.
    biometric_consent: bool

    @field_validator("biometric_consent")
    @classmethod
    def _must_consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Consent to biometric processing is required to verify your identity.")
        return v


class IdentityStatusResponse(Schema):
    status: str
    verification_id: UUID | None = None
    similarity: float | None = None
    threshold: float | None = None
    decision_reason: str | None = None
    extracted_name: str | None = None
    #: Only ever the masked form. The full number never leaves the database.
    cnic_masked: str | None = None
    expiry_date: str | None = None
    submitted_at: datetime | None = None


class RequestOtpRequest(Schema):
    phone_number: str = Field(
        min_length=8, max_length=20, description="E.164 format, e.g. +923001234567"
    )


class RequestOtpResponse(Schema):
    phone_number_id: UUID
    masked_number: str
    expires_at: datetime
    #: Populated only when the console SMS sender is active (development), so
    #: the offline demo can complete the flow. Never set in a deployed env.
    debug_code: str | None = None


class VerifyOtpRequest(Schema):
    code: str = Field(min_length=4, max_length=8, pattern=r"^\d+$")


class SubmitBusinessVerificationRequest(Schema):
    legal_name: str = Field(min_length=2, max_length=200)
    registration_number: str = Field(min_length=2, max_length=80)
    document_file_id: UUID


class DeviceFingerprintRequest(Schema):
    fingerprint: str = Field(min_length=16, max_length=256)
    user_agent: str | None = None
    screen_resolution: str | None = Field(default=None, max_length=20)
    timezone: str | None = Field(default=None, max_length=60)
    languages: str | None = Field(default=None, max_length=120)


class VerificationChecklistItem(Schema):
    key: str
    label: str
    status: str
    points_available: int
    action_url: str | None = None


class VerificationStatusResponse(Schema):
    identity: str
    phone: str
    email: str
    device: str
    checklist: list[VerificationChecklistItem]


__all__ = [
    "DeviceFingerprintRequest",
    "IdentityStatusResponse",
    "RequestOtpRequest",
    "RequestOtpResponse",
    "SubmitBusinessVerificationRequest",
    "SubmitIdentityRequest",
    "UploadIntentRequest",
    "UploadIntentResponse",
    "VerificationChecklistItem",
    "VerificationStatusResponse",
    "VerifyOtpRequest",
]
