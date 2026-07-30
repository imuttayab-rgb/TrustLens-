"""Email and SMS delivery jobs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from trustlens.shared.logging import get_logger

log = get_logger(__name__)


async def send_email(
    ctx: dict[str, Any], *, to: str, template: str, context: dict[str, Any], subject: str = ""
) -> dict[str, Any]:
    await ctx["email"].send(to=to, subject=subject, template=template, context=context)
    # `to` is masked by the logging redaction processor; the template name is
    # what actually matters for debugging.
    log.info("email_sent", template=template, to=to)
    return {"sent": True, "template": template}


async def send_otp_sms(
    ctx: dict[str, Any], *, to: str, code: str, ttl_minutes: int = 5
) -> dict[str, Any]:
    await ctx["sms"].send(
        to=to,
        message=(
            f"Your TrustLens verification code is {code}. "
            f"It expires in {ttl_minutes} minutes. Never share this code."
        ),
    )
    # The code itself is NEVER logged - the redaction processor would strip it,
    # but it is not passed here in the first place.
    log.info("otp_sent", to=to)
    return {"sent": True}


async def send_security_alert(ctx: dict[str, Any], *, user_id: str, reason: str) -> dict[str, Any]:
    """Notify a user that their sessions were revoked.

    Reaching here means refresh-token reuse was detected, i.e. someone held a
    copy of their session. Telling them is not optional.
    """
    uow = ctx["uow"]()
    async with uow:
        user = await uow.users.get(UUID(user_id))
    if user is None:
        return {"skipped": "user not found"}

    await ctx["email"].send(
        to=user.email.value,
        subject="Security alert on your TrustLens account",
        template="security_alert",
        context={"reason": reason},
    )
    log.critical("security_alert_sent", user_id=user_id, reason=reason)
    return {"sent": True}


__all__ = ["send_email", "send_otp_sms", "send_security_alert"]
