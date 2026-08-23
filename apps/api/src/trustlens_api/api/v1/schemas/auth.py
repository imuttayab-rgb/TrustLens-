"""Auth request/response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from trustlens_api.api.v1.schemas.common import Schema


class RegisterRequest(Schema):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    full_name: str = Field(min_length=2, max_length=150)
    as_seller: bool = False
    accepted_terms: bool = Field(description="Must be true; recorded in `consents`.")

    @field_validator("accepted_terms")
    @classmethod
    def _must_accept(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must accept the terms and privacy policy to register.")
        return v


class RegisterResponse(Schema):
    user_id: UUID | None
    status: str
    #: Always true, even for a duplicate address - the endpoint must not
    #: become a user-enumeration oracle.
    verification_email_sent: bool = True
    message: str = "Check your email to confirm your address."


class LoginRequest(Schema):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    device_fingerprint: str | None = Field(default=None, max_length=256)


class UserSummary(Schema):
    id: UUID
    email: EmailStr
    full_name: str
    status: str
    roles: list[str]
    permissions: list[str]
    email_verified: bool
    mfa_enabled: bool
    has_seller_profile: bool = False


class LoginResponse(Schema):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(description="Access-token lifetime in seconds.")
    user: UserSummary
    #: The refresh token is NOT here - it is set as an httpOnly cookie so an
    #: XSS payload cannot read it (ADR-0006).


class MfaRequiredResponse(Schema):
    mfa_required: bool = True
    mfa_token: str


class VerifyEmailRequest(Schema):
    token: str = Field(min_length=16, max_length=256)


class ForgotPasswordRequest(Schema):
    email: EmailStr


class ResetPasswordRequest(Schema):
    token: str = Field(min_length=16, max_length=256)
    password: str = Field(min_length=12, max_length=128)


class ChangePasswordRequest(Schema):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class SessionSummary(Schema):
    id: UUID
    created_at: datetime
    expires_at: datetime
    ip_address: str | None
    user_agent: str | None
    is_current: bool = False


class DeleteAccountRequest(Schema):
    password: str = Field(min_length=1, max_length=128)


__all__ = [
    "ChangePasswordRequest",
    "DeleteAccountRequest",
    "ForgotPasswordRequest",
    "LoginRequest",
    "LoginResponse",
    "MfaRequiredResponse",
    "RegisterRequest",
    "RegisterResponse",
    "ResetPasswordRequest",
    "SessionSummary",
    "UserSummary",
    "VerifyEmailRequest",
]
