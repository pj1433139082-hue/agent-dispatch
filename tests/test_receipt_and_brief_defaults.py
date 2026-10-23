from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: evidence

## What to build

写 hello.txt。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: hello.txt
- Verify: python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('hello.txt').exists() else 1)"

## Acceptance

- [ ] hello.txt 存在。
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


def start_run(tmp_path: Path) -> Path:
    assert run_dispatch(tmp_path, "render", "01", "--agent", "lead").returncode == 0
    assert run_dispatch(tmp_path, "start", "01").returncode == 0
    return sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]


def test_receipt_can_reference_a_worktree_file_as_evidence(tmp_path: Path) -> None:
    repo(tmp_path)
    run_dir = start_run(tmp_path)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    worktree = Path(run["execution_root"])
    if not worktree.is_absolute():
        worktree = tmp_path / worktree
    (worktree / "hello.txt").write_text("hello", encoding="utf-8")
    (run_dir / "receipt.json").write_text(json.dumps({
        "ticket_id": "01", "run_id": run["run_id"], "status": "done", "summary": "ok",
        "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "file", "path": "hello.txt"}]}],
    }), encoding="utf-8")

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode == 0, result.stdout + result.stderr


def test_setup_turns_the_brief_gate_on_by_default(tmp_path: Path) -> None:
    repo(tmp_path)
    assert run_dispatch(tmp_path, "setup").returncode == 0

    refused = run_dispatch(tmp_path, "render", "01", "--agent", "lead")

    assert refused.returncode != 0
    assert "brief" in (refused.stdout + refused.stderr).lower()
