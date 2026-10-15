"""Verify and copy a release, with reversible source backups and no host Python dependency.

Called by update-existing.sh inside the existing API image. Real credentials,
Docker volumes, git history and uploads never appear in a release manifest.
"""

from __future__ import annotations
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile

PORT_KEYS = {'API_PORT', 'WEB_PORT', 'ADMIN_PORT', 'STORAGE_PORT',
             'MINIO_CONSOLE_PORT', 'MAILPIT_UI_PORT'}


def compatible_port_config(raw: bytes) -> bytes:
    """Normalize old IP:port values for Compose's separate bind-address prefix.

    Only public port settings change. Do not source/evaluate the private env file;
    preserve credentials, comments and Windows line endings byte for byte.
    Conflicting explicit interfaces fail before any source/configuration mutation.
    """
    lines = raw.decode('utf-8').splitlines(keepends=True)
    records = {}
    pattern = re.compile(
        r'(?P<prefix>[ \t]*(?:export[ \t]+)?(?P<key>[A-Z_]+)[ \t]*=[ \t]*)'
        r'(?P<value>"[^"\r\n]*"|\x27[^\x27\r\n]*\x27|[^#\r\n]*?)'
        r'(?P<suffix>[ \t]*(?:#[^\r\n]*)?)(?P<ending>\r?\n|$)'
    )
    for index, line in enumerate(lines):
        match = pattern.fullmatch(line)
        if not match or match['key'] not in PORT_KEYS | {'LOCAL_BIND_ADDRESS'}:
            continue
        key = match['key']
        if key in records:
            raise ValueError('Duplicate port setting; consolidate assignments: ' + key)
        value = match['value'].strip()
        quote = value[:1] if value[:1] in {'"', "'"} else ''
        records[key] = (index, match, value[1:-1] if quote else value, quote)

    def address(value: str) -> str:
        parsed = ipaddress.ip_address(value.strip('[]'))
        return '[' + str(parsed) + ']' if parsed.version == 6 else str(parsed)

    binding = records.get('LOCAL_BIND_ADDRESS')
    explicit_bind = address(binding[2]) if binding and binding[2] else None
    legacy_hosts = set()
    replacements = {}
    for key, (index, match, value, quote) in records.items():
        if key not in PORT_KEYS or not value:
            continue
        if ':' in value:
            host, port = value.rsplit(':', 1)
            try:
                host = address(host)
            except ValueError:
                raise ValueError('Invalid legacy bind address in ' + key) from None
            legacy_hosts.add(host)
        else:
            port = value
        if not port.isascii() or not port.isdigit() or not 1 <= int(port) <= 65535:
            raise ValueError('Invalid local port in ' + key)
        if ':' in value:
            replacements[index] = match['prefix'] + quote + str(int(port)) + quote + match['suffix'] + match['ending']
    if not replacements:
        return raw
    if len(legacy_hosts) != 1 or (explicit_bind and explicit_bind not in legacy_hosts):
        raise ValueError('Conflicting port bind addresses; resolve explicit interfaces before updating')
    host = next(iter(legacy_hosts))
    for index, replacement in replacements.items():
        lines[index] = replacement
    if binding:
        index, match, _, quote = binding
        lines[index] = match['prefix'] + quote + host + quote + match['suffix'] + match['ending']
    elif host != '127.0.0.1':
        ending = '\r\n' if b'\r\n' in raw else '\n'
        if lines and not lines[-1].endswith('\n'):
            lines[-1] += ending
        lines.append('LOCAL_BIND_ADDRESS=' + host + ending)
    return ''.join(lines).encode('utf-8')


def write_config(path: Path, contents: bytes) -> None:
    """Replace private config atomically, preserving existing owner and permissions."""
    if path.is_symlink():
        raise ValueError('Private configuration must not be a symlink')
    descriptor, filename = tempfile.mkstemp(prefix='.env.production.update-', dir=path.parent)
    temporary = Path(filename)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            info = path.stat()
            shutil.copystat(path, temporary)
            if hasattr(os, 'geteuid') and os.geteuid() == 0:
                os.chown(temporary, info.st_uid, info.st_gid)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def progress(phase: str, done: int, total: int) -> None:
    """Flush counters so Docker/Git Bash show work during slow Windows bind mounts."""
    if done == 0 or done % 100 == 0 or done == total:
        print(f'{phase}: {done}/{total} files', flush=True)

PROTECTED = {
    ".env",
    ".env.production",
    ".git",
    ".trustlens-calls",
    ".trustlens-update-backups",
    "node_modules",
    ".venv",
    ".next",
}


def safe_path(root: Path, name: str) -> Path:
    """Reject traversal, symlinks and protected runtime state before any mutation."""
    rel = PurePosixPath(name)
    if (
        not name
        or rel.is_absolute()
        or "\\" in name
        or any(p in {"..", ".", ""} or p in PROTECTED for p in rel.parts)
    ):
        raise ValueError("Unsafe/protected release path")
    path = root.joinpath(*rel.parts)
    for parent in [path, *path.parents]:
        if parent == root.parent:
            break
        if parent.is_symlink():
            raise ValueError("Release paths must not traverse symlinks")
    return path


def stage(release: Path, target: Path, backup: Path) -> None:
    """Verify the complete manifest before modifying even one existing file."""
    config = target / '.env.production'
    if config.is_symlink():
        raise ValueError('Private configuration must not be a symlink')
    original_config = config.read_bytes() if config.exists() else None
    updated_config = compatible_port_config(original_config) if original_config is not None else None
    entries = []
    manifest_lines = (release / "MANIFEST.sha256").read_text().splitlines()
    progress('Verifying release', 0, len(manifest_lines))
    for index, line in enumerate(manifest_lines, 1):
        digest, name = line.split("  ", 1)
        source = safe_path(release, name)
        destination = safe_path(target, name)
        if len(digest) != 64 or hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise ValueError("Release checksum mismatch: " + name)
        if destination.exists() and not destination.is_file():
            raise ValueError("Target path is not a regular file: " + name)
        entries.append(name)
        progress('Verifying release', index, len(manifest_lines))
    entries.append("MANIFEST.sha256")
    backup.mkdir(parents=True, exist_ok=False)
    state = []
    progress('Backing up source', 0, len(entries))
    for index, name in enumerate(entries, 1):
        destination = safe_path(target, name)
        exists = destination.exists()
        if exists:
            saved = backup / "source" / name
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, saved)
        state.append({"path": name, "existed": exists})
        progress('Backing up source', index, len(entries))
    # Journal is complete before copying; interrupted updates can restore every file.
    (backup / "source-state.json").write_text(json.dumps(state))
    if original_config != updated_config:
        private_backup = backup / 'private-config' / '.env.production'
        private_backup.parent.mkdir(mode=0o700)
        shutil.copy2(config, private_backup)
        write_config(config, updated_config)
        print('LEGACY_PORT_FORMAT_UPDATED; credentials and key values preserved', flush=True)
    progress('Copying release', 0, len(entries))
    for index, name in enumerate(entries, 1):
        destination = safe_path(target, name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(safe_path(release, name), destination)
        progress('Copying release', index, len(entries))
    print("SOURCE_STAGED; credentials and key values preserved", flush=True)


def restore(target: Path, backup: Path) -> None:
    """Restore previous managed files; remove only files created by this update."""
    journal = backup / 'source-state.json'
    if not journal.is_file():
        print('SOURCE_UNCHANGED; no completed copy journal', flush=True)
        return
    state = json.loads(journal.read_text())
    private_backup = backup / 'private-config' / '.env.production'
    if private_backup.is_file():
        write_config(target / '.env.production', private_backup.read_bytes())
        print('PREVIOUS_PORT_CONFIGURATION_RESTORED', flush=True)
    progress('Restoring source', 0, len(state))
    for index, item in enumerate(state, 1):
        destination = safe_path(target, item["path"])
        if item["existed"]:
            shutil.copy2(backup / "source" / item["path"], destination)
        elif destination.is_file():
            destination.unlink()
        progress('Restoring source', index, len(state))
    print("SOURCE_ROLLBACK_COMPLETE", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["stage", "restore"])
    parser.add_argument("--release", type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--backup", required=True, type=Path)
    args = parser.parse_args()
    if args.action == "stage":
        stage(args.release, args.target, args.backup)
    else:
        restore(args.target, args.backup)
