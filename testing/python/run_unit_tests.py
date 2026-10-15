"""Run isolated unit/API-contract tests with ephemeral credentials, never a real .env.

Uses dummy endpoints; tests needing a real database have their own explicit opt-in.
Install dev dependencies first: uv sync --all-packages --dev.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
import secrets
import subprocess
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def environment(root: Path) -> dict[str, str]:
    """Synthetic configuration for import-time app construction; no saved credentials."""
    env = dict(os.environ)
    for name in list(env):
        if name.startswith(("SECURITY_", "DATABASE_", "STORAGE_", "CALLS_", "CHAT_TEST_")):
            del env[name]
    key = Ed25519PrivateKey.generate()
    encode = lambda value: base64.b64encode(value).decode("ascii")
    env.update(
        ENV="test",
        USE_FAKE_AI="true",
        DEBUG="false",
        DATABASE_URL="postgresql+asyncpg://test:test@127.0.0.1:1/test",
        DATABASE_URL_SYNC="postgresql+psycopg://test:test@127.0.0.1:1/test",
        REDIS_URL="redis://127.0.0.1:1/0",
        REDIS_QUEUE_URL="redis://127.0.0.1:1/1",
        SECURITY_JWT_ALGORITHM="EdDSA",
        SECURITY_JWT_ISSUER="http://localhost:8000",
        SECURITY_JWT_AUDIENCE="trustlens-web",
        SECURITY_JWT_PRIVATE_KEY=encode(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        ),
        SECURITY_JWT_PUBLIC_KEY=encode(
            key.public_key().public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
            )
        ),
        SECURITY_OTP_PEPPER=encode(secrets.token_bytes(32)),
        SECURITY_TOKEN_PEPPER=encode(secrets.token_bytes(32)),
        SECURITY_ENCRYPTION_KEY=encode(secrets.token_bytes(32)),
        STORAGE_ACCESS_KEY_ID="synthetic-test",
        STORAGE_SECRET_ACCESS_KEY=secrets.token_hex(24),
    )
    sources = ["apps/api/src", "apps/worker/src", "apps/ml/src"]
    sources += [str(p.relative_to(root)) for p in (root / "packages/py").glob("*/src")]
    env["PYTHONPATH"] = os.pathsep.join(str(root / p) for p in sources)
    return env


def main() -> int:
    """Keep exit status intact so the same command can serve as a CI gate."""
    root = Path(__file__).resolve().parents[2]
    args = sys.argv[1:] or [
        "packages/py",
        "apps/api/tests",
        "apps/worker/tests",
        "-m",
        "not integration",
        "--tb=short",
    ]
    return subprocess.call([sys.executable, "-m", "pytest", *args], cwd=root, env=environment(root))


if __name__ == "__main__":
    raise SystemExit(main())
