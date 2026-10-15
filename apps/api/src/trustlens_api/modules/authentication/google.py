"""Google OAuth 2.0 authorization-code exchange.

Deliberately not a domain port: nothing in trustlens.core needs to fake
Google, because the use case it feeds (AuthenticateWithGoogle) only ever
sees an already-resolved, already-verified email and name. This lives
entirely at the transport edge, the same place the JWT and cookie handling
for every other auth flow lives.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from trustlens.shared.config.settings import GoogleAuthSettings

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - a URL, not a credential
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class GoogleOAuthError(Exception):
    """Google rejected the code, or the token/userinfo exchange failed."""


@dataclass(frozen=True, slots=True)
class GoogleUserInfo:
    email: str
    name: str


def build_authorize_url(settings: GoogleAuthSettings, *, state: str) -> str:
    params = {
        "client_id": settings.client_id,
        "redirect_uri": settings.redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        # Always show the account chooser rather than silently reusing
        # whichever Google account happens to be signed in in this browser -
        # a shared/lab machine makes the alternative a real footgun.
        "prompt": "select_account",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code(settings: GoogleAuthSettings, *, code: str) -> GoogleUserInfo:
    """Trade a one-time authorization code for the caller's verified email
    and name.

    Two round trips, not one: the token exchange proves the code is genuine
    (it requires our client secret, which only this server holds), and only
    the resulting access token is then used to ask Google who it belongs to.
    Reading userinfo from an unverified code would be answering the wrong
    question.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        token_response = await client.post(
            TOKEN_URL,
            data={
                "client_id": settings.client_id,
                "client_secret": (
                    settings.client_secret.get_secret_value() if settings.client_secret else ""
                ),
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.redirect_uri,
            },
        )
        if token_response.status_code != 200:
            raise GoogleOAuthError(
                f"Google rejected the authorization code (HTTP {token_response.status_code})."
            )
        access_token = token_response.json().get("access_token")
        if not access_token:
            raise GoogleOAuthError("Google's token response carried no access token.")

        userinfo_response = await client.get(
            USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
        )
        if userinfo_response.status_code != 200:
            raise GoogleOAuthError(
                f"Could not read the Google profile (HTTP {userinfo_response.status_code})."
            )
        payload = userinfo_response.json()

    email = payload.get("email")
    if not email or not payload.get("email_verified"):
        # Google can return an unverified address for some account types
        # (e.g. a Workspace account mid-migration). Treating it as proof of
        # ownership when Google itself will not would defeat the entire
        # point of skipping our own verification step for this flow.
        raise GoogleOAuthError("Google did not return a verified email address.")

    return GoogleUserInfo(email=email, name=payload.get("name") or email)


__all__ = ["GoogleOAuthError", "GoogleUserInfo", "build_authorize_url", "exchange_code"]
