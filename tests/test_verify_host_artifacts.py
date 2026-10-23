from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: host artifacts

## What to build

写 out.txt。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: out.txt
- Verify: python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('out.txt').exists() else 1)"

## Acceptance

- [ ] out.txt 存在。
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def prepare(tmp_path: Path) -> Path:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)
    assert run_dispatch(tmp_path, "render", "01", "--agent", "lead").returncode == 0
    assert run_dispatch(tmp_path, "start", "01").returncode == 0
    return sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]


def test_host_hook_artifacts_do_not_fail_the_scope_check(tmp_path: Path) -> None:
    run_dir = prepare(tmp_path)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    worktree = Path(run["execution_root"])
    if not worktree.is_absolute():
        worktree = tmp_path / worktree
    (worktree / "out.txt").write_text("ok", encoding="utf-8")
    hooks = worktree / ".dsh-hooks"
    hooks.mkdir()
    (hooks / "context.md").write_text("host wrote this", encoding="utf-8")
    (run_dir / "receipt.json").write_text(json.dumps({
        "ticket_id": "01", "run_id": run["run_id"], "status": "done", "summary": "ok",
        "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
    }), encoding="utf-8")

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode == 0, result.stdout + result.stderr


def test_verify_on_a_failed_ticket_points_at_retry(tmp_path: Path) -> None:
    run_dir = prepare(tmp_path)
    state_path = tmp_path / ".dispatch" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["tickets"]["01"]["state"] = "failed"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode != 0
    assert "dispatch retry 01" in (result.stdout + result.stderr)
