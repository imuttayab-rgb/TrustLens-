"""Source update/rollback contracts. No Docker daemon or real project data needed."""

from pathlib import Path
import hashlib
import importlib.util
import os
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("updater", ROOT / "scripts/local/update_source.py")
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


def release(root, files):
    root.mkdir()
    lines = []
    for name, body in files.items():
        p = root / name
        p.parent.mkdir(exist_ok=True, parents=True)
        p.write_text(body)
        lines.append(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + name)
    (root / "MANIFEST.sha256").write_text("\n".join(lines) + "\n")


def test_stage_and_restore_preserve_config_unmanaged_files_and_runtime(tmp_path):
    source, target = tmp_path / "release", tmp_path / "existing with spaces"
    release(source, {"app.py": "new", "new/module.py": "added"})
    target.mkdir()
    (target / "app.py").write_text("old")
    (target / ".env.production").write_text("PRIVATE_KEY=synthetic")
    (target / "custom.txt").write_text("user work")
    backup = target / ".trustlens-update-backups/test"
    updater.stage(source, target, backup)
    assert (target / "app.py").read_text() == "new"
    assert (target / ".env.production").read_text() == "PRIVATE_KEY=synthetic"
    updater.restore(target, backup)
    assert (target / "app.py").read_text() == "old"
    assert not (target / "new/module.py").exists()
    assert (target / "custom.txt").read_text() == "user work"


@pytest.mark.parametrize(
    "name",
    [
        "../outside",
        ".env.production",
        ".git/config",
        "node_modules/test",
        "/tmp/outside",
        "bad\\path",
    ],
)
def test_manifest_rejects_runtime_and_traversal_paths(tmp_path, name):
    with pytest.raises(ValueError):
        updater.safe_path(tmp_path, name)


def test_corrupt_manifest_never_starts_copying(tmp_path):
    source, target = tmp_path / "release", tmp_path / "target"
    target.mkdir()
    release(source, {"app.py": "new"})
    (source / "app.py").write_text("tampered")
    (target / "app.py").write_text("original")
    with pytest.raises(ValueError):
        updater.stage(source, target, target / "backup")
    assert (target / "app.py").read_text() == "original" and not (target / "backup").exists()


def test_update_build_failure_restores_source_without_stopping_services(tmp_path):
    source, target = tmp_path / "release", tmp_path / "target with spaces"
    target.mkdir()
    scripts = {
        name: (ROOT / name).read_text()
        for name in ["scripts/local/update-existing.sh", "scripts/local/update_source.py"]
    }
    scripts["app.py"] = "new"
    release(source, scripts)
    (target / "app.py").write_text("old")
    (target / ".env.production").write_text("KEY=unchanged\nAPI_PORT=127.0.0.1:8000\n")
    binary = tmp_path / "bin"
    binary.mkdir()
    log = tmp_path / "commands.txt"
    docker = binary / "docker"
    docker.write_text(
        f"#!{sys.executable}\n"
        + """import os,sys,subprocess
from pathlib import Path
args=sys.argv[1:]
with open(os.environ['FAKE_LOG'],'a') as out:out.write(repr(args)+'\\n')
if args[0]=='inspect':print(os.environ['FAKE_TARGET']+'/docker/compose/docker-compose.prod.yml' if 'config_files' in args[2] else 'sha256:'+'1'*64)
elif args[0]=='compose' and 'ps' in args:print('existing-'+args[-1])
elif args[0]=='compose' and 'build' in args and args[-1]=='web':sys.exit(27)
elif args[0]=='run':
    mounts={}
    for i,a in enumerate(args):
        if a=='-v':
            local,remote=args[i+1].split(':',1);mounts[remote.removesuffix(':ro')]=local
    start=args.index('/release/scripts/local/update_source.py')
    command=[sys.executable]
    for arg in args[start:]:
        for remote,local in mounts.items():
            if arg==remote or arg.startswith(remote+'/'):arg=local+arg[len(remote):];break
        command.append(arg)
    sys.exit(subprocess.call(command))
"""
    )
    docker.chmod(0o755)
    env = {
        **os.environ,
        "PATH": str(binary) + os.pathsep + os.environ["PATH"],
        "FAKE_LOG": str(log),
        "FAKE_TARGET": str(target),
    }
    result = subprocess.run(
        ["bash", str(source / "scripts/local/update-existing.sh"), str(target), "trustlens"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 27, result.stdout + result.stderr
    assert (target / "app.py").read_text() == "old"
    assert (target / ".env.production").read_text() == "KEY=unchanged\nAPI_PORT=127.0.0.1:8000\n"
    assert "'stop'" not in log.read_text() and "'down'" not in log.read_text()
    assert not (target / ".trustlens-update-lock").exists()
