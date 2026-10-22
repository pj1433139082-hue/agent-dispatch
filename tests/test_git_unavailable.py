from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: gitgate

## What to build

x

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: src/**/*.py
- Verify: python -c "print(1)"

## Acceptance

- [ ] x
"""


def run_dispatch(tmp_path: Path, *args: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    if env_extra:
        env.update(env_extra)
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=tmp_path, env=env, text=True, capture_output=True, check=False)


def prepare(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)


BROKEN_GIT = {"GIT_DIR": str(Path("C:/definitely-not-a-git-dir"))}


def test_render_fails_loudly_when_git_is_unusable(tmp_path: Path) -> None:
    prepare(tmp_path)

    result = run_dispatch(tmp_path, "render", "01", env_extra=BROKEN_GIT)

    assert result.returncode != 0
    assert "base commit" in (result.stderr + result.stdout).lower() or "git" in (result.stderr + result.stdout).lower()
    assert not list((tmp_path / ".dispatch" / "runs").glob("*/run.json")), "不许留下半成品 run"


def test_claim_fails_closed_when_git_is_unusable(tmp_path: Path) -> None:
    prepare(tmp_path)
    assert run_dispatch(tmp_path, "render", "01", "--no-worktree").returncode == 0

    result = run_dispatch(tmp_path, "claim", "01", "--json", env_extra=BROKEN_GIT)

    assert result.returncode == 4, result.stdout + result.stderr
    assert "scope" in (result.stdout + result.stderr).lower()
