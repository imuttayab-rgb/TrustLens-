"""Portable launcher contracts using a fake Docker CLI, not a Docker engine.

Exercises configuration preservation, isolated project names and failure handling.
Actual image builds, Windows path mounting and engine startup need Docker Desktop.
"""

from pathlib import Path
import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def installation(tmp_path):
    root = tmp_path / "project with spaces"
    root.mkdir()
    shutil.copytree(ROOT / "scripts", root / "scripts")
    shutil.copy(ROOT / ".env.production.example", root / ".env.production.example")
    binary = tmp_path / "bin"
    binary.mkdir()
    docker = binary / "docker"
    docker.write_text(
        f"#!{sys.executable}\n"
        + """import json, os, subprocess, sys
from pathlib import Path
args=sys.argv[1:]
with open(os.environ['DOCKER_TEST_LOG'],'a') as f: f.write(json.dumps(args)+'\\n')
if args[:1]==['info'] and os.environ.get('DOCKER_TEST_DOWN'): sys.exit(1)
if 'build' in args and args[-1]=='web' and os.environ.get('DOCKER_TEST_FAIL_BUILD'): sys.exit(27)
if 'run' in args and '/workspace/scripts/configure_calls.py' in args:
    root=Path(args[args.index('--volume')+1].rsplit(':/workspace',1)[0])
    sys.exit(subprocess.call([sys.executable,str(root/'scripts/configure_calls.py'),'--root',str(root)]))
sys.exit(0)
"""
    )
    docker.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{binary}{os.pathsep}{os.environ['PATH']}",
        "DOCKER_TEST_LOG": str(tmp_path / "docker.jsonl"),
    }
    env.pop("TRUSTLENS_LOCAL_PROJECT", None)
    return root, env


def run(root, env):
    return subprocess.run(
        ["bash", "scripts/local/start.sh"], cwd=root, env=env, capture_output=True, text=True
    )


def test_fresh_setup_preserves_secrets_and_isolates_project(installation):
    root, env = installation
    first = run(root, env)
    assert first.returncode == 0, first.stderr
    content = (root / ".env.production").read_text()
    assert "change-me-before-first-boot" not in "\n".join(
        line for line in content.splitlines() if not line.startswith("#")
    )
    values = dict(
        line.split("=", 1)
        for line in content.splitlines()
        if "=" in line and not line.startswith("#")
    )
    for name in ("SECURITY_ENCRYPTION_KEY", "POSTGRES_PASSWORD", "CALLS_LIVEKIT_API_SECRET"):
        assert values[name] and values[name] not in first.stdout
    assert values["CALLS_ENABLED"] == "true"
    # Parse the full generated file as the containers do, including optional empty values.
    config_env = {
        **env,
        **values,
        "PYTHONPATH": os.pathsep.join(
            str(ROOT / path)
            for path in ["packages/py/trustlens-core/src", "packages/py/trustlens-shared/src"]
        ),
    }
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from trustlens.shared.config import Settings; s=Settings(); assert s.calls.calls_enabled; assert s.ai.classifier_threshold is None",
        ],
        cwd=root,
        env=config_env,
        check=True,
        capture_output=True,
    )
    second = run(root, env)
    assert second.returncode == 0, second.stderr
    assert (root / ".env.production").read_text() == content
    calls = [json.loads(line) for line in Path(env["DOCKER_TEST_LOG"]).read_text().splitlines()]
    assert all(
        c[c.index("--project-name") + 1] == "trustlens-clean"
        for c in calls
        if "--project-name" in c
    )
    assert not any("down" in c or "rm" in c or "-v" in c for c in calls)
    assert not (root / ".trustlens-setup-lock").exists()


def test_build_failure_leaves_private_config_and_does_not_start_services(installation):
    root, env = installation
    result = run(root, {**env, "DOCKER_TEST_FAIL_BUILD": "1"})
    assert result.returncode == 27
    assert "Setup stopped" in result.stderr
    assert (root / ".env.production").is_file()
    assert not (root / ".trustlens-setup-lock").exists()
    assert not any(
        "up" in json.loads(line) for line in Path(env["DOCKER_TEST_LOG"]).read_text().splitlines()
    )


def test_missing_engine_does_not_create_config(installation):
    root, env = installation
    result = run(root, {**env, "DOCKER_TEST_DOWN": "1"})
    assert result.returncode != 0
    assert "Start Docker Desktop" in result.stderr
    assert not (root / ".env.production").exists()


def test_existing_setup_lock_prevents_a_second_writer(installation):
    root, env = installation
    (root / ".trustlens-setup-lock").mkdir()
    assert run(root, env).returncode != 0
    assert not (root / ".env.production").exists()
