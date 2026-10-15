"""Encrypted chat archive and database-stream backup helper.

Run inside the API container. Never prints credentials or message contents.
"""

from __future__ import annotations
import argparse
import asyncio
import base64
import hashlib
import json
import sys
from pathlib import Path
from uuid import uuid4
from sqlalchemy import select, func
from trustlens.db import models as m
from trustlens.db.session import create_engine, create_session_factory
from trustlens.shared.config.settings import Settings
from trustlens.shared.crypto import EnvelopeEncryptor
from trustlens.shared.storage import build_storage

TABLES = [
    m.ConversationModel,
    m.MessageModel,
    m.ChatLifecycleModel,
    m.ChatClearModel,
    m.ChatVoiceModel,
    m.ChatVersionModel,
    m.ChatAuditModel,
    m.ChatCaseModel,
    m.ChatCallModel,
    m.ChatCallRuntimeModel,
]


def enc(settings):
    return EnvelopeEncryptor(
        key=settings.security.aes_key(), key_id=settings.security.encryption_key_id
    )


async def export_archive(directory, settings):
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "objects").mkdir()
    cipher = enc(settings)
    storage = build_storage(settings.storage)
    engine = create_engine(settings.database)
    factory = create_session_factory(engine)
    manifest = {"version": 1, "files": {}, "objects": [], "rows": {}}
    try:
        async with factory() as session:
            for model in TABLES:
                name = model.__tablename__
                count = 0
                path = directory / f"{name}.jsonl.enc"
                with path.open("w") as out:
                    async for row in (
                        await session.stream(
                            select(model.__table__).execution_options(yield_per=500)
                        )
                    ).mappings():
                        out.write(
                            cipher.encrypt(
                                json.dumps(dict(row), default=str),
                                associated_data=f"chat-archive/{name}".encode(),
                            )
                            + "\n"
                        )
                        count += 1
                manifest["rows"][name] = count
                manifest["files"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            voices = (await session.execute(select(m.ChatVoiceModel))).scalars().all()
            for voice in voices:
                for kind, key in [
                    ("original", voice.original_key),
                    ("playback", voice.playback_key),
                ]:
                    raw = await storage.get(bucket=voice.bucket, object_key=key)
                    digest = hashlib.sha256(raw).hexdigest()
                    path = directory / "objects" / f"{digest}.enc"
                    path.write_bytes(raw)
                    manifest["files"][str(path.relative_to(directory))] = digest
                    manifest["objects"].append(
                        {
                            "file": str(path.relative_to(directory)),
                            "bucket": voice.bucket,
                            "key": key,
                            "messageId": str(voice.message_id),
                            "kind": kind,
                            "originalSha256": voice.sha256,
                        }
                    )
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2))
        (directory / "manifest.enc").write_text(
            cipher.encrypt(json.dumps(manifest), associated_data=b"chat-archive/manifest")
        )
        print(json.dumps({"exported": manifest["rows"], "voiceObjects": len(manifest["objects"])}))
    finally:
        await engine.dispose()


async def verify_archive(directory, settings, restore=False):
    cipher = enc(settings)
    manifest = json.loads(
        cipher.decrypt(
            (directory / "manifest.enc").read_text(), associated_data=b"chat-archive/manifest"
        )
    )
    storage = build_storage(settings.storage)
    for relative, digest in manifest["files"].items():
        path = (directory / relative).resolve()
        if (
            not path.is_relative_to(directory.resolve())
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            raise ValueError("Archive integrity check failed")
        if relative.endswith(".jsonl.enc"):
            table = relative.removesuffix(".jsonl.enc")
            for line in path.read_text().splitlines():
                json.loads(cipher.decrypt(line, associated_data=f"chat-archive/{table}".encode()))
    for item in manifest["objects"]:
        raw = (directory / item["file"]).read_bytes()
        decoded = base64.b64decode(
            cipher.decrypt(raw.decode(), associated_data=item["messageId"].encode())
        )
        if (
            item["kind"] == "original"
            and hashlib.sha256(decoded).hexdigest() != item["originalSha256"]
        ):
            raise ValueError("Voice original checksum mismatch")
        if restore:
            if await storage.exists(bucket=item["bucket"], object_key=item["key"]):
                if await storage.get(bucket=item["bucket"], object_key=item["key"]) != raw:
                    raise ValueError("Existing object differs; refusing to overwrite it")
            else:
                await storage.put(
                    bucket=item["bucket"],
                    object_key=item["key"],
                    data=raw,
                    content_type="application/octet-stream",
                    server_side_encryption=False,
                )
    print(
        json.dumps(
            {
                "verified": True,
                "voiceObjects": len(manifest["objects"]),
                "restoredMissingObjects": restore,
            }
        )
    )


def stream_backup(mode, settings):
    cipher = enc(settings)
    sequence = 0
    if mode == "encrypt":
        backup_id = str(uuid4())
        sys.stdout.buffer.write(("TRUSTLENS-DB-ENC-1:" + backup_id + "\n").encode())
        while block := sys.stdin.buffer.read(1024 * 1024):
            token = cipher.encrypt(
                base64.b64encode(block).decode(),
                associated_data=f"db-backup/{backup_id}/{sequence}".encode(),
            )
            sys.stdout.write(token + "\n")
            sequence += 1
        sys.stdout.write(
            cipher.encrypt("END", associated_data=f"db-backup/{backup_id}/{sequence}".encode())
            + "\n"
        )
    else:
        header = sys.stdin.buffer.readline().decode().strip()
        if not header.startswith("TRUSTLENS-DB-ENC-1:"):
            raise ValueError("Invalid backup format")
        backup_id = header.split(":", 1)[1]
        ended = False
        for line in sys.stdin.buffer:
            value = cipher.decrypt(
                line.decode().strip(), associated_data=f"db-backup/{backup_id}/{sequence}".encode()
            )
            sequence += 1
            if value == "END":
                ended = True
                break
            sys.stdout.buffer.write(base64.b64decode(value))
        if not ended or sys.stdin.buffer.read(1):
            raise ValueError("Incomplete or extra backup data")


async def status(settings, warn_bytes):
    engine = create_engine(settings.database)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            messages = (
                await session.execute(select(func.count()).select_from(m.MessageModel))
            ).scalar_one()
            count, size = (
                await session.execute(
                    select(func.count(), func.coalesce(func.sum(m.ChatVoiceModel.size_bytes), 0))
                )
            ).one()
            print(
                json.dumps(
                    {
                        "messages": messages,
                        "voiceMessages": count,
                        "originalVoiceBytes": int(size),
                        "warning": int(size) >= warn_bytes,
                        "note": "Original bytes only; allow extra space for playback copies, encryption, database and backups.",
                    }
                )
            )
            return 2 if int(size) >= warn_bytes else 0
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode", choices=["export", "verify", "restore-objects", "encrypt", "decrypt", "status"]
    )
    parser.add_argument("directory", nargs="?")
    parser.add_argument("--warn-bytes", type=int, default=10 * 1024**3)
    args = parser.parse_args()
    settings = Settings()
    if args.mode in ("encrypt", "decrypt"):
        stream_backup(args.mode, settings)
    elif args.mode == "status":
        sys.exit(asyncio.run(status(settings, args.warn_bytes)))
    else:
        if not args.directory:
            parser.error("directory is required")
        path = Path(args.directory)
        if args.mode == "export":
            asyncio.run(export_archive(path, settings))
        else:
            asyncio.run(verify_archive(path, settings, args.mode == "restore-objects"))


if __name__ == "__main__":
    main()
