"""Refresh-cookie handling.

Every attribute here is a security decision:

* HttpOnly  - JavaScript (including an XSS payload) cannot read it.
* Secure    - never transmitted over plain HTTP outside local development.
* SameSite=Lax - blocks cross-site POSTs, which is the CSRF vector for the
                 one cookie-authenticated endpoint we have.
* Path      - the cookie is not even SENT to any endpoint except /auth, so a
              compromised unrelated route cannot leak it in a log or a proxy.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import Response

from trustlens.shared.config.settings import Settings

COOKIE_NAME = "tl_rt"
COOKIE_PATH = "/api/v1/auth"


def set_refresh_cookie(
    response: Response, settings: Settings, *, token: str, expires_at: datetime
) -> None:
    max_age = int((expires_at - datetime.now(expires_at.tzinfo)).total_seconds())
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=max(max_age, 0),
        httponly=True,
        secure=settings.env.is_deployed,
        samesite="lax",
        path=COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        secure=settings.env.is_deployed,
        samesite="lax",
        path=COOKIE_PATH,
    )


__all__ = ["COOKIE_NAME", "COOKIE_PATH", "clear_refresh_cookie", "set_refresh_cookie"]
