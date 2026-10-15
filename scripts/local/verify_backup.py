"""Encrypt and verify a materialized pg_dump without Windows host pipelines.

Run in the new API image with the existing installation's environment. Temporary
plaintext stays in the private backup directory and is removed on success/error.
"""

import hashlib
from pathlib import Path
import subprocess
import sys

directory = Path(sys.argv[1])
raw, encrypted, restored = [
    directory / name for name in ("database.dump", "database.dump.enc", "verify.dump")
]
module = "trustlens_api.modules.messaging.archive"
try:
    with raw.open("rb") as source, encrypted.open("wb") as output:
        subprocess.run(
            [sys.executable, "-m", module, "encrypt"], stdin=source, stdout=output, check=True
        )
    with encrypted.open("rb") as source, restored.open("wb") as output:
        subprocess.run(
            [sys.executable, "-m", module, "decrypt"], stdin=source, stdout=output, check=True
        )
    with raw.open("rb") as source, restored.open("rb") as decoded:
        if (
            hashlib.file_digest(source, "sha256").digest()
            != hashlib.file_digest(decoded, "sha256").digest()
        ):
            raise RuntimeError("Database backup verification failed")
    with encrypted.open("rb") as archive:
        checksum = hashlib.file_digest(archive, "sha256").hexdigest()
    (directory / "database.sha256").write_text(checksum + "  database.dump.enc\n")
    print("DATABASE_BACKUP_VERIFIED")
finally:
    raw.unlink(missing_ok=True)
    restored.unlink(missing_ok=True)
