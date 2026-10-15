"""Regression coverage for old IP:port settings, source rollback and visible progress."""
from pathlib import Path
import hashlib
import importlib.util
import ipaddress
import re
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('port_updater', ROOT / 'scripts/local/update_source.py')
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


@pytest.mark.parametrize('key', sorted(updater.PORT_KEYS))
def test_legacy_loopback_ports_are_normalized_without_changing_other_bytes(key):
    original = (f'# saved config\r\n{key}=\"127.0.0.1:8080\" # local\r\n'
                'SECURITY_ENCRYPTION_KEY=unchanged==\r\n'
                'DATABASE_URL=postgresql://user:unchanged@postgres/db\r\n').encode()
    expected = original.replace(b'"127.0.0.1:8080"', b'"8080"')
    assert updater.compatible_port_config(original) == expected
    assert updater.compatible_port_config(expected) == expected


@pytest.mark.parametrize('original', [
    b'WEB_PORT=3000\nAPI_PORT=8000\n',
    b'# WEB_PORT=127.0.0.1:3000\nPRIVATE=do-not-evaluate-$(anything)\n',
    b'WEB_PORT=\nAPI_PORT=""\n',
])
def test_modern_or_default_config_remains_identical(original):
    assert updater.compatible_port_config(original) == original


@pytest.mark.parametrize(('value', 'binding'), [
    ('192.168.1.4:3010', '192.168.1.4'),
    ('0.0.0.0:3010', '0.0.0.0'),
    ('[::1]:3010', '[::1]'),
])
def test_explicit_interfaces_and_custom_ports_are_preserved(value, binding):
    original = ('WEB_PORT=' + value).encode()
    expected = ('WEB_PORT=3010\nLOCAL_BIND_ADDRESS=' + binding + '\n').encode()
    assert updater.compatible_port_config(original) == expected


@pytest.mark.parametrize('value', [
    b'WEB_PORT=127.0.0.1:3000\nAPI_PORT=192.168.1.4:8000\n',
    b'LOCAL_BIND_ADDRESS=0.0.0.0\nWEB_PORT=127.0.0.1:3000\n',
    b'WEB_PORT=127.0.0.1:70000\n',
    b'WEB_PORT=127.0.0.1:0\n',
    b'WEB_PORT=127.0.0.1:3000\nWEB_PORT=3001\n',
    b'WEB_PORT=$(touch something)\n',
])
def test_ambiguous_invalid_or_executable_port_values_are_rejected(value):
    with pytest.raises(ValueError):
        updater.compatible_port_config(value)


def test_whitespace_export_quotes_and_matching_explicit_interface():
    original = b"export WEB_PORT = '127.0.0.1:3000' # local\nLOCAL_BIND_ADDRESS=127.0.0.1\n"
    assert updater.compatible_port_config(original) == original.replace(b'127.0.0.1:3000', b'3000')


def project(tmp_path, env):
    release, target = tmp_path / 'release', tmp_path / 'target'
    release.mkdir()
    target.mkdir()
    (release / 'app.py').write_text('new')
    (release / 'MANIFEST.sha256').write_text(hashlib.sha256(b'new').hexdigest() + '  app.py\n')
    (target / 'app.py').write_text('old')
    (target / '.env.production').write_bytes(env)
    return release, target, target / '.trustlens-update-backups/test'


def test_source_and_private_port_config_restore_byte_for_byte(tmp_path, capsys):
    original = b'API_PORT=127.0.0.1:8000\r\nSECRET=preserve-this\r\n'
    release, target, backup = project(tmp_path, original)
    updater.stage(release, target, backup)
    assert (target / '.env.production').read_bytes() == original.replace(b'127.0.0.1:8000', b'8000')
    assert (backup / 'private-config/.env.production').read_bytes() == original
    assert (target / 'app.py').read_text() == 'new'
    updater.restore(target, backup)
    assert (target / '.env.production').read_bytes() == original
    assert (target / 'app.py').read_text() == 'old'
    output = capsys.readouterr().out
    assert 'preserve-this' not in output
    assert all(phase in output for phase in ['Verifying release:', 'Backing up source:', 'Copying release:', 'Restoring source:'])


def test_invalid_ports_fail_before_backup_or_source_mutation(tmp_path):
    original = b'API_PORT=127.0.0.1:8000\nWEB_PORT=0.0.0.0:3000\n'
    release, target, backup = project(tmp_path, original)
    with pytest.raises(ValueError):
        updater.stage(release, target, backup)
    assert not backup.exists()
    assert (target / '.env.production').read_bytes() == original
    assert (target / 'app.py').read_text() == 'old'
    updater.restore(target, backup)
    assert (target / 'app.py').read_text() == 'old'


def test_failure_after_port_migration_is_recoverable(tmp_path, monkeypatch):
    original = b'WEB_PORT=127.0.0.1:3000\nSECRET=original\n'
    release, target, backup = project(tmp_path, original)
    copy = updater.shutil.copy2

    def interrupted_copy(source, destination):
        if Path(source) == release / 'app.py':
            raise OSError('synthetic interrupted file copy')
        return copy(source, destination)

    monkeypatch.setattr(updater.shutil, 'copy2', interrupted_copy)
    with pytest.raises(OSError):
        updater.stage(release, target, backup)
    updater.restore(target, backup)
    assert (target / '.env.production').read_bytes() == original
    assert (target / 'app.py').read_text() == 'old'


def test_six_compose_bindings_have_exactly_one_host_address():
    original = '\n'.join(f'{key}=127.0.0.1:{3000 + index}' for index, key in enumerate(sorted(updater.PORT_KEYS))).encode()
    normalized = dict(line.split('=', 1) for line in updater.compatible_port_config(original).decode().splitlines())
    compose = (ROOT / 'docker/compose/docker-compose.prod.yml').read_text()
    mappings = re.findall(r"^\s+- '(\$\{LOCAL_BIND_ADDRESS[^']+)'$", compose, re.MULTILINE)
    assert len(mappings) == 6
    for mapping in mappings:
        expanded = re.sub(r'\$\{([A-Z_]+):-([^}]+)\}',
                          lambda match: normalized.get(match[1], match[2]), mapping)
        host, published, container = expanded.split(':')
        assert ipaddress.ip_address(host).is_loopback
        assert 1 <= int(published) <= 65535 and 1 <= int(container) <= 65535
