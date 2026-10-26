from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: hello

**What to build:** x
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


def test_dirty_main_checkout_message_says_how_to_fix(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    (tmp_path / ".dispatch").mkdir()
    (tmp_path / ".dispatch" / "config.json").write_text(
        json.dumps({"persona_policy": "off", "require_brief": False}), encoding="utf-8"
    )
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)

    assert run_dispatch(tmp_path, "render", "01", "--agent", "lead").returncode == 0
    run_dispatch(tmp_path, "start", "01")

    run_dir = next((tmp_path / ".dispatch" / "runs").glob("*/"))
    run_dir.joinpath("receipt.json").write_text(json.dumps({
        "ticket_id": "01",
        "run_id": run_dir.name,
        "status": "done",
        "summary": "ok",
        "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
    }), encoding="utf-8")
    worktree = next((tmp_path / ".dispatch" / "worktrees").glob("*/"))
    (worktree / "hello.txt").write_text("hello", encoding="utf-8")

    # setup 会写 .gitignore 但不提交；这就是真实的新项目第一次 verify 会撞的坑
    (tmp_path / ".gitignore").write_text(".dispatch/\n", encoding="utf-8")

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "commit them first" in combined, combined
