from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: hook

## What to build

写 out.txt。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: out.txt
- Verify: python -c "print(1)"

## Acceptance

- [ ] out.txt 存在。
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def repo(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)


def test_install_hooks_writes_a_guarded_pre_commit(tmp_path: Path) -> None:
    repo(tmp_path)

    result = run_dispatch(tmp_path, "install-hooks")

    assert result.returncode == 0
    hook = tmp_path / ".git" / "hooks" / "pre-commit"
    text = hook.read_text(encoding="utf-8")
    assert "[ -d .dispatch ] || exit 0" in text
    assert "wrap --root ." in text
    assert "--no-verify" not in text.split("echo")[0]


def test_install_hooks_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    repo(tmp_path)
    assert run_dispatch(tmp_path, "install-hooks").returncode == 0

    again = run_dispatch(tmp_path, "install-hooks")

    assert again.returncode == 1
    assert "--force" in again.stderr


def test_the_command_the_hook_runs_matches_wrap_exit_codes(tmp_path: Path) -> None:
    """钩子只是包了一层 `dispatch wrap`，所以校验收口命令本身的退出码。"""
    repo(tmp_path)
    assert run_dispatch(tmp_path, "wrap").returncode == 0

    (tmp_path / "stray.txt").write_text("x", encoding="utf-8")
    dirty = run_dispatch(tmp_path, "wrap")

    assert dirty.returncode == 1
    assert "will block land" in dirty.stdout
