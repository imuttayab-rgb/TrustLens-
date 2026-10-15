"""Generate private localhost calling config. Run using the API Python environment.

No third-party account is created; existing keys are preserved on rerun.
For public servers use docs/operations/voice-calls.md.
"""

import argparse
import base64
import json
import os
from pathlib import Path
import re
import secrets
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization


def configure(root: Path, subject: str | None = None):
    env = root / ".env.production"
    content = env.read_text(encoding="utf-8-sig")

    def value(key):
        values = re.findall(r"^" + re.escape(key) + r"=(.*)$", content, re.M)
        return values[-1].strip().strip("\"'") if values else ""

    if value("CALLS_LIVEKIT_URL") and value("CALLS_LIVEKIT_URL") != "ws://localhost:7880":
        raise SystemExit(
            "Existing non-local calling configuration preserved. Use the deployment guide."
        )
    public_web = value("WEB_BASE_URL")
    if public_web and not public_web.startswith(("http://localhost:", "http://127.0.0.1:")):
        raise SystemExit("This script is for localhost. Public URLs require the deployment setup.")
    key = value("CALLS_LIVEKIT_API_KEY") or "tl_" + secrets.token_hex(12)
    secret = value("CALLS_LIVEKIT_API_SECRET") or secrets.token_urlsafe(48)
    updates = {
        "CALLS_ENABLED": "true",
        "CALLS_LIVEKIT_URL": "ws://localhost:7880",
        "CALLS_LIVEKIT_INTERNAL_URL": "http://livekit:7880",
        "CALLS_LIVEKIT_API_KEY": key,
        "CALLS_LIVEKIT_API_SECRET": secret,
    }
    if subject:
        if not (subject.startswith("mailto:") and "@" in subject) and not subject.startswith(
            "https://"
        ):
            raise SystemExit("Push subject must be a real mailto: contact or public HTTPS URL.")
        if value("CALLS_VAPID_PRIVATE_KEY"):
            updates["CALLS_VAPID_SUBJECT"] = subject
        else:
            private = ec.generate_private_key(ec.SECP256R1())
            b64 = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")
            updates.update(
                CALLS_VAPID_PRIVATE_KEY=b64(
                    private.private_bytes(
                        serialization.Encoding.DER,
                        serialization.PrivateFormat.PKCS8,
                        serialization.NoEncryption(),
                    )
                ),
                CALLS_VAPID_PUBLIC_KEY=b64(
                    private.public_key().public_bytes(
                        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
                    )
                ),
                CALLS_VAPID_SUBJECT=subject,
            )
    for k, v in updates.items():
        if re.search(r"^" + k + r"=", content, re.M):
            content = re.sub(r"^" + k + r"=.*$", lambda _: k + "=" + v, content, flags=re.M)
        else:
            content = content.rstrip() + "\n" + k + "=" + v + "\n"
    directory = root / ".trustlens-calls"
    directory.mkdir(mode=0o700, exist_ok=True)
    config = {
        "port": 7880,
        "bind_addresses": ["0.0.0.0"],
        "rtc": {
            "tcp_port": 7881,
            "udp_port": 7882,
            "node_ip": "127.0.0.1",
            "use_external_ip": False,
            "enable_loopback_candidate": True,
        },
        "keys": {key: secret},
        "room": {"auto_create": False},
        "logging": {"level": "warn"},
    }
    # JSON is valid YAML and safely quotes generated key values.
    target = directory / "livekit.yaml"
    target.write_text(json.dumps(config, indent=2) + "\n")
    target.chmod(0o600)
    staged = env.with_name(".env.production.calls-tmp")
    staged.write_text(content)
    staged.chmod(0o600)
    os.replace(staged, env)
    print("LOCAL_CALL_CONFIG_READY; existing API and VAPID keys preserved; no secrets printed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--push-subject", help="Optional real contact, e.g. mailto:operations@your-domain.com"
    )
    args = parser.parse_args()
    configure(args.root.resolve(), args.push_subject)
