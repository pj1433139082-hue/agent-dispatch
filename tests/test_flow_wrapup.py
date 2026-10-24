from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: v

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


def test_doctor_warns_about_files_that_will_block_land(tmp_path: Path) -> None:
    repo(tmp_path)
    (tmp_path / "stray.txt").write_text("x", encoding="utf-8")

    result = run_dispatch(tmp_path, "doctor")

    assert "will block land" in (result.stdout + result.stderr)
    assert "stray.txt" in result.stdout


def test_doctor_does_not_warn_about_dispatch_internal_dirs(tmp_path: Path) -> None:
    repo(tmp_path)
    (tmp_path / ".dispatch").mkdir(exist_ok=True)
    (tmp_path / ".dispatch" / "state.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".scratch").mkdir()
    (tmp_path / ".scratch" / "x.md").write_text("x", encoding="utf-8")

    result = run_dispatch(tmp_path, "doctor")

    assert "stray.txt" not in result.stdout
    assert ".scratch" not in result.stdout


def test_status_prints_a_session_wrap_up_hint_when_work_is_open(tmp_path: Path) -> None:
    repo(tmp_path)
    assert run_dispatch(tmp_path, "render", "01", "--agent", "lead", "--no-worktree").returncode == 0

    result = run_dispatch(tmp_path, "status")

    assert "Session wrap-up" in result.stdout
    assert "active run" in result.stdout
