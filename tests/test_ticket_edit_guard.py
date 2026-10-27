from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: edit

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


def repo_with_run(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)
    assert run_dispatch(tmp_path, "render", "01", "--agent", "lead", "--no-worktree").returncode == 0


def test_status_flags_a_ticket_edited_after_render(tmp_path: Path) -> None:
    repo_with_run(tmp_path)
    ticket = tmp_path / "tickets" / "01.md"
    ticket.write_text(ticket.read_text(encoding="utf-8") + "\n<!-- edited -->\n", encoding="utf-8")

    result = run_dispatch(tmp_path, "status")

    assert "票在 render 后被改过" in result.stdout, result.stdout


def test_doctor_reports_tickets_edited_after_render(tmp_path: Path) -> None:
    repo_with_run(tmp_path)
    ticket = tmp_path / "tickets" / "01.md"
    ticket.write_text(ticket.read_text(encoding="utf-8") + "\n<!-- edited -->\n", encoding="utf-8")

    result = run_dispatch(tmp_path, "doctor")

    assert "tickets edited after render" in (result.stdout + result.stderr)
