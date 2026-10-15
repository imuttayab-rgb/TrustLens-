"""Email and SMS adapters.

Every provider sits behind a port with a console fallback, so the whole system
runs offline with no paid key (NFR-8) - which is what makes the FYP
demonstrable on a lab machine.
"""

from __future__ import annotations

from email.message import EmailMessage
from trustlens.core.domain.errors import ExternalServiceError
from typing import Any

import aiosmtplib
import httpx

from trustlens.core.domain.ports import EmailSender, SmsSender
from trustlens.shared.config.settings import NotificationSettings
from trustlens.shared.logging import get_logger

log = get_logger(__name__)

#: Minimal built-in templates. Rendering stays deliberately simple: HTML email
#: templating is not where this project's complexity budget should go.
TEMPLATES: dict[str, tuple[str, str]] = {
    "verify_email": (
        "Confirm your TrustLens email address",
        "Hello {full_name},\n\nConfirm your email address to continue:\n"
        "{web_base_url}/verify-email/{token}\n\nThis link expires in 24 hours.\n",
    ),
    "reset_password": (
        "Reset your TrustLens password",
        "A password reset was requested for your account.\n\n"
        "{web_base_url}/reset-password/{token}\n\nThis link expires in 15 minutes.\n"
        "If this was not you, you can ignore this email.\n",
    ),
    "registration_attempt_existing_account": (
        "Someone tried to register with your email",
        "Someone attempted to create a TrustLens account with this address.\n"
        "If it was you, sign in instead - your account already exists.\n",
    ),
    "identity_verified": (
        "Your identity has been verified",
        "Good news - your identity check passed and your Trust Score has been updated.\n",
    ),
    "identity_rejected": (
        "We could not verify your identity",
        "Your identity check did not pass.\n\nReason: {reason}\n\n"
        "You can submit new documents or appeal this decision.\n",
    ),
    "appeal_resolved": (
        "Your appeal has been reviewed",
        "Your appeal has been {decision}.\n\n{note}\n",
    ),
    "security_alert": (
        "Security alert on your TrustLens account",
        "We revoked your sessions because of suspicious activity ({reason}).\n"
        "Please sign in again. If this was not you, change your password.\n",
    ),
}


class SmtpEmailSender(EmailSender):
    def __init__(self, settings: NotificationSettings, *, web_base_url: str) -> None:
        self._s = settings
        self._web_base_url = web_base_url

    async def send(self, *, to: str, subject: str, template: str, context: dict[str, Any]) -> None:
        default_subject, body = TEMPLATES.get(template, (subject, "{body}"))
        message = EmailMessage()
        message["From"] = f"{self._s.email_from_name} <{self._s.email_from}>"
        message["To"] = to
        message["Subject"] = subject or default_subject
        message.set_content(body.format(web_base_url=self._web_base_url, **{"body": "", **context}))
        await aiosmtplib.send(
            message,
            hostname=self._s.smtp_host,
            port=self._s.smtp_port,
            username=self._s.smtp_user or None,
            password=(self._s.smtp_password.get_secret_value() if self._s.smtp_password else None),
            start_tls=self._s.smtp_tls,
        )


class ResendEmailSender(EmailSender):
    def __init__(self, api_key: str, settings: NotificationSettings, *, web_base_url: str) -> None:
        self._api_key = api_key
        self._s = settings
        self._web_base_url = web_base_url

    async def send(self, *, to: str, subject: str, template: str, context: dict[str, Any]) -> None:
        default_subject, body = TEMPLATES.get(template, (subject, "{body}"))
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "from": f"{self._s.email_from_name} <{self._s.email_from}>",
                    "to": [to],
                    "subject": subject or default_subject,
                    "text": body.format(web_base_url=self._web_base_url, **{"body": "", **context}),
                },
            )
            response.raise_for_status()


class TwilioSmsSender(SmsSender):
    def __init__(self, account_sid: str, auth_token: str, from_number: str) -> None:
        self._sid = account_sid
        self._token = auth_token
        self._from = from_number

    async def send(self, *, to: str, message: str) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{self._sid}/Messages.json",
                auth=(self._sid, self._token),
                data={"To": to, "From": self._from, "Body": message},
            )
            response.raise_for_status()


class LocalSmsInboxSender(SmsSender):
    """Free localhost OTP preview in Mailpit; codes never enter application logs.

    The SMTP sink is bound to loopback by the local compose setup. This adapter
    is rejected by production configuration and does not send a real SMS.
    """

    def __init__(self, settings: NotificationSettings) -> None:
        self._email = SmtpEmailSender(settings, web_base_url="http://localhost:3000")

    async def send(self, *, to: str, message: str) -> None:
        await self._email.send(
            to="sms@localhost.test",
            subject="TrustLens local SMS preview",
            template="local_sms",
            context={"body": f"Recipient: {to}\n{message}"},
        )


class DisabledSmsSender(SmsSender):
    async def send(self, *, to: str, message: str) -> None:
        raise ExternalServiceError(
            "sms", "Phone verification is unavailable. Please contact support."
        )


def build_email_sender(settings: NotificationSettings, *, web_base_url: str) -> EmailSender:
    if settings.email_provider == "resend":
        if not settings.resend_api_key:
            raise ValueError("RESEND_API_KEY is required for the selected email provider")
        return ResendEmailSender(
            settings.resend_api_key.get_secret_value(), settings, web_base_url=web_base_url
        )
    # Old local 'console' configs now use the local SMTP inbox, preserving demo
    # verification without printing credentials. Production rejects console.
    return SmtpEmailSender(settings, web_base_url=web_base_url)


def build_sms_sender(settings: NotificationSettings) -> SmsSender:
    if settings.sms_provider == "twilio":
        if not (
            settings.twilio_account_sid
            and settings.twilio_auth_token
            and settings.twilio_from_number
        ):
            raise ValueError("Twilio SID, auth token and sender are required")
        return TwilioSmsSender(
            settings.twilio_account_sid,
            settings.twilio_auth_token.get_secret_value(),
            settings.twilio_from_number,
        )
    if settings.sms_provider == "disabled":
        return DisabledSmsSender()
    return LocalSmsInboxSender(settings)


__all__ = [
    "TEMPLATES",
    "ResendEmailSender",
    "SmtpEmailSender",
    "TwilioSmsSender",
    "build_email_sender",
    "build_sms_sender",
]
