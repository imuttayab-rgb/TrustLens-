"""Cryptographic adapters: password hashing, token hashing, JWT, envelope encryption.

Everything one-way is one-way, and everything reversible carries a key id so
it can be rotated without a migration outage.
"""

from __future__ import annotations

import base64
import contextlib
import hmac
import json
import secrets
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import UUID

import jwt
import pyotp
from argon2 import PasswordHasher as _Argon2
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from trustlens.shared.config.settings import SecuritySettings

# ── Passwords ────────────────────────────────────────────────────────


class Argon2PasswordHasher:
    """argon2id password hashing.

    Chosen over bcrypt because it is memory-hard and therefore far more
    expensive to attack on GPUs; it is the current OWASP recommendation.
    Parameters live in config so they can be raised as hardware improves, and
    the hash string records its own parameters so old hashes stay verifiable.
    """

    #: A precomputed hash of a random value, used to burn identical CPU when
    #: the account does not exist. Without it, login response time reveals
    #: which email addresses are registered.
    _DUMMY_PASSWORD = secrets.token_urlsafe(32)

    def __init__(self, settings: SecuritySettings) -> None:
        self._hasher = _Argon2(
            memory_cost=settings.argon2_memory_kib,
            time_cost=settings.argon2_time_cost,
            parallelism=settings.argon2_parallelism,
        )
        self._dummy_hash = self._hasher.hash(self._DUMMY_PASSWORD)

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, InvalidHashError, ValueError):
            return False

    def verify_dummy(self) -> None:
        """Constant-work path for a non-existent account.

        The verification is EXPECTED to fail - burning identical CPU is the
        entire point, so the exception is suppressed rather than handled.
        """
        with contextlib.suppress(Exception):
            self._hasher.verify(self._dummy_hash, "not-the-password")

    def needs_rehash(self, password_hash: str) -> bool:
        try:
            return self._hasher.check_needs_rehash(password_hash)
        except InvalidHashError:
            return True


# ── Opaque tokens (refresh, verification, API keys) ──────────────────


class PepperedTokenHasher:
    """Hashing for high-entropy opaque tokens.

    SHA-256 with a server-side pepper, not argon2: these values are already
    256 bits of entropy, so key stretching buys nothing and would make token
    refresh needlessly slow. The pepper lives outside the database, so a
    database leak alone does not let an attacker match stolen hashes.
    """

    def __init__(self, pepper: bytes) -> None:
        self._pepper = pepper

    def new_token(self, nbytes: int = 32) -> str:
        return secrets.token_urlsafe(nbytes)

    def hash_token(self, raw: str) -> bytes:
        return hmac.new(self._pepper, raw.encode(), sha256).digest()

    def compare(self, raw: str, expected: bytes) -> bool:
        return hmac.compare_digest(self.hash_token(raw), expected)


class OtpCodeGenerator:
    """Numeric one-time codes, hashed with a distinct pepper.

    A separate pepper from refresh tokens so that compromising one does not
    compromise the other.
    """

    def __init__(self, pepper: bytes) -> None:
        self._pepper = pepper

    def generate(self, length: int = 6) -> str:
        # secrets, not random: an OTP generated from a predictable PRNG is not
        # a second factor.
        return "".join(secrets.choice("0123456789") for _ in range(length))

    def hash_code(self, code: str) -> bytes:
        return hmac.new(self._pepper, code.encode(), sha256).digest()

    def verify_code(self, code: str, code_hash: bytes) -> bool:
        return hmac.compare_digest(self.hash_code(code), code_hash)


# ── API keys ─────────────────────────────────────────────────────────


class ApiKeyFactory:
    """Generates and verifies partner API keys.

    Format: `tl_live_<10-hex id>.<43-char secret>`.

    The prefix is stored in the clear and indexed so lookup is one equality
    match; only then is the secret half compared in constant time. Hashing
    alone would force a scan over every key to find a candidate.
    """

    def __init__(self, prefix: str, hasher: Argon2PasswordHasher) -> None:
        self._prefix = prefix
        self._hasher = hasher

    #: Separates the lookup prefix from the secret. A dot rather than an
    #: underscore because the prefix itself contains underscores
    #: (`tl_live_a1b2c3`) - splitting on one would be ambiguous, and a secret
    #: that happened to contain the delimiter would silently fail to verify.
    SEPARATOR = "."

    def generate(self) -> tuple[str, str, bytes]:
        """Returns (full_key, key_prefix, key_hash). The full key is shown once."""
        identifier = secrets.token_hex(5)
        secret = secrets.token_urlsafe(32)
        key_prefix = f"{self._prefix}_{identifier}"
        full_key = f"{key_prefix}{self.SEPARATOR}{secret}"
        return full_key, key_prefix, self._hasher.hash(secret).encode()

    @classmethod
    def split(cls, full_key: str) -> tuple[str, str] | None:
        """Split a presented key into (prefix, secret), or None if malformed."""
        prefix, separator, secret = full_key.partition(cls.SEPARATOR)
        if not separator or not prefix or not secret:
            return None
        return prefix, secret

    def verify(self, secret: str, key_hash: bytes) -> bool:
        return self._hasher.verify(secret, key_hash.decode())


# ── Envelope encryption for sensitive PII ────────────────────────────


class EnvelopeEncryptor:
    """AES-256-GCM encryption for CNIC numbers, dates of birth and MFA secrets.

    The key id is stored alongside the ciphertext, so rotation is a background
    re-encrypt rather than a migration outage: new writes use the current key
    while old values remain readable under their original one.

    Format: `v1.<key_id>.<base64(nonce||ciphertext)>`
    """

    _VERSION = "v1"

    def __init__(self, key: bytes, key_id: str, *, previous_keys: dict[str, bytes] | None = None):
        if len(key) != 32:
            raise ValueError("encryption key must be exactly 32 bytes (AES-256)")
        self._aead = AESGCM(key)
        self._key_id = key_id
        self._previous = {kid: AESGCM(k) for kid, k in (previous_keys or {}).items()}

    def encrypt(self, plaintext: str, *, associated_data: bytes | None = None) -> str:
        nonce = secrets.token_bytes(12)
        ciphertext = self._aead.encrypt(nonce, plaintext.encode(), associated_data)
        blob = base64.urlsafe_b64encode(nonce + ciphertext).decode()
        return f"{self._VERSION}.{self._key_id}.{blob}"

    def decrypt(self, token: str, *, associated_data: bytes | None = None) -> str:
        try:
            version, key_id, blob = token.split(".", 2)
        except ValueError as exc:
            raise ValueError("malformed ciphertext") from exc
        if version != self._VERSION:
            raise ValueError(f"unsupported ciphertext version {version!r}")

        aead = self._aead if key_id == self._key_id else self._previous.get(key_id)
        if aead is None:
            raise ValueError(f"no key available for key id {key_id!r}")

        raw = base64.urlsafe_b64decode(blob)
        return aead.decrypt(raw[:12], raw[12:], associated_data).decode()

    def blind_index(self, plaintext: str, pepper: bytes) -> bytes:
        """A deterministic HMAC for equality search over encrypted values.

        This is what makes duplicate-CNIC detection possible while the number
        itself stays encrypted at rest: the index is searchable, the value is
        not readable.
        """
        return hmac.new(pepper, plaintext.encode(), sha256).digest()


# ── JWT ──────────────────────────────────────────────────────────────


class JwtService:
    """Access-token issuing and verification.

    EdDSA (Ed25519) rather than HS256: the API signs, and any future extracted
    service can verify without ever holding the signing key.
    """

    def __init__(self, settings: SecuritySettings) -> None:
        self._settings = settings
        self._private = settings.pem_private_key()
        self._public = settings.pem_public_key()
        self._alg = settings.jwt_algorithm

    def issue_access_token(
        self,
        *,
        user_id: UUID,
        roles: list[str],
        permissions: list[str],
        permission_version: int,
        session_id: UUID | None,
        jti: UUID,
        now: datetime,
    ) -> tuple[str, datetime]:
        expires_at = now + timedelta(minutes=self._settings.access_token_ttl_minutes)
        payload: dict[str, Any] = {
            "iss": self._settings.jwt_issuer,
            "aud": self._settings.jwt_audience,
            "sub": str(user_id),
            "jti": str(jti),
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "typ": "access",
            "roles": roles,
            "perms": permissions,
            # Compared against a Redis counter on each request, so a revoked
            # role takes effect in seconds instead of one token lifetime.
            "pv": permission_version,
            "sid": str(session_id) if session_id else None,
        }
        # Never put PII in here: a JWT is signed, NOT encrypted - anyone
        # holding it can read every claim.
        token = jwt.encode(payload, self._private, algorithm=self._alg)
        return token, expires_at

    def decode(self, token: str) -> dict[str, Any]:
        return jwt.decode(
            token,
            self._public,
            algorithms=[self._alg],
            audience=self._settings.jwt_audience,
            issuer=self._settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub", "jti"]},
        )


def sign_webhook_payload(secret: bytes, body: bytes, timestamp: int) -> str:
    """`t=<ts>,v1=<hmac>` - lets partners verify authenticity and reject replays."""
    signed = f"{timestamp}.".encode() + body
    digest = hmac.new(secret, signed, sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


class HmacResponseSigner:
    """Signs public API responses so a marketplace can prove what we said.

    A Trust Score is a claim about a person that money moves on. A marketplace
    receiving one over a compromised proxy, or from a cache it does not
    control, has no way to distinguish it from a score an attacker wrote -
    unless it is signed. This is P6-04, and it is what makes the public API
    quotable rather than merely readable.

    The timestamp is inside the signed material, not beside it. Signing the
    body alone would let anyone replay a captured "score: 95" response
    indefinitely, which is precisely the attack a scammer wants.

    Same `t=<ts>,v1=<hmac>` shape as the webhook signature, so a partner
    writes one verification routine rather than two.
    """

    def __init__(self, secret: bytes, key_id: str = "s1", *, max_age_seconds: int = 300) -> None:
        self._secret = secret
        self._key_id = key_id
        self._max_age = max_age_seconds

    @property
    def key_id(self) -> str:
        return self._key_id

    def sign(self, payload: bytes, *, timestamp: int) -> str:
        return sign_webhook_payload(self._secret, payload, timestamp)

    def verify(self, payload: bytes, *, timestamp: int, signature: str) -> bool:
        """Constant-time check of a signature this service produced.

        Exists so the contract is testable from the partner's side: a
        signature nobody can verify is decoration.
        """
        expected = self.sign(payload, timestamp=timestamp)
        return hmac.compare_digest(expected, signature)

    def is_fresh(self, timestamp: int, *, now: int) -> bool:
        # Rejects both a stale replay and a timestamp from the future, which
        # would otherwise extend a captured response's life indefinitely.
        return -self._max_age <= (now - timestamp) <= self._max_age


# ── TOTP (staff MFA) ────────────────────────────────────────────────


class PyotpTotpProvider:
    """RFC 6238 TOTP, via `pyotp`. The secret itself is never handled here -
    callers encrypt/decrypt it separately (`EnvelopeEncryptor`); this class
    only ever sees a secret already in hand for the duration of one call."""

    def generate_secret(self) -> str:
        return pyotp.random_base32()

    def provisioning_uri(self, secret: str, *, account_name: str, issuer: str) -> str:
        return pyotp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=issuer)

    def verify_code(self, secret: str, code: str) -> bool:
        # valid_window=1 tolerates one 30s step of clock drift either way -
        # tight enough that a stolen code is still only briefly useful.
        return pyotp.TOTP(secret).verify(code, valid_window=1)


def stable_json(value: Any) -> str:
    """Deterministic JSON for hashing and idempotency fingerprints."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def fingerprint(value: Any) -> str:
    return sha256(stable_json(value).encode()).hexdigest()


__all__ = [
    "ApiKeyFactory",
    "Argon2PasswordHasher",
    "EnvelopeEncryptor",
    "HmacResponseSigner",
    "JwtService",
    "OtpCodeGenerator",
    "PepperedTokenHasher",
    "PyotpTotpProvider",
    "fingerprint",
    "sign_webhook_payload",
    "stable_json",
]
