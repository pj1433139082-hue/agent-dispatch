from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: link

## What to build

x

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: **
- Verify: python -c "print(1)"

## Acceptance

- [ ] x
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def make_junction(link: Path, target: Path) -> bool:
    if os.name != "nt":
        try:
            link.symlink_to(target, target_is_directory=True)
            return True
        except OSError:
            return False
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True)
    return result.returncode == 0 and link.exists()


def test_verify_refuses_a_write_that_escapes_through_a_junction(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    project = tmp_path / "project"
    (project / "tickets").mkdir(parents=True)
    (project / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=project, check=True, capture_output=True)
    assert run_dispatch(project, "render", "01", "--agent", "lead").returncode == 0
    assert run_dispatch(project, "start", "01").returncode == 0
    run_dir = sorted((project / ".dispatch" / "runs").iterdir())[0]
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    worktree = Path(run["execution_root"])
    if not worktree.is_absolute():
        worktree = project / worktree
    if not make_junction(worktree / "link", outside):
        pytest.skip("this platform cannot create junctions/symlinks without extra privileges")

    (worktree / "link" / "leak.txt").write_text("leaked", encoding="utf-8")
    (worktree / "out.txt").write_text("ok", encoding="utf-8")
    (run_dir / "receipt.json").write_text(json.dumps({
        "ticket_id": "01", "run_id": run["run_id"], "status": "done", "summary": "ok",
        "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
    }), encoding="utf-8")

    result = run_dispatch(project, "verify", "01")

    assert (outside / "leak.txt").exists(), "前提：确实写到仓库外了"
    assert result.returncode != 0
    assert "symlink" in (result.stdout + result.stderr).lower() or "junction" in (result.stdout + result.stderr).lower()
