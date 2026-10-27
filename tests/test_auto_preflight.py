from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: preflight

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

EXECUTOR = """import json, os, pathlib
run = pathlib.Path(os.environ["DISPATCH_RUN_DIR"])
pathlib.Path("out.txt").write_text("ok", encoding="utf-8")
run.joinpath("receipt.json").write_text(json.dumps({
    "ticket_id": "01", "run_id": os.environ["DISPATCH_RUN_ID"], "status": "done", "summary": "ok",
    "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
}), encoding="utf-8")
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def repo(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    (tmp_path / "exec.py").write_text(EXECUTOR, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)


def ghost_index(tmp_path: Path) -> None:
    state = {"version": 1, "tickets": {"01": {"run_id": "ghost", "state": "failed", "updated_at": "2026-10-23T00:00:00+00:00"}}}
    (tmp_path / ".dispatch").mkdir(exist_ok=True)
    (tmp_path / ".dispatch" / "state.json").write_text(json.dumps(state), encoding="utf-8")


def test_auto_refuses_to_run_on_a_broken_index(tmp_path: Path) -> None:
    repo(tmp_path)
    ghost_index(tmp_path)

    result = run_dispatch(tmp_path, "auto", "01", "--executor", "python exec.py")

    assert result.returncode != 0
    text = (result.stdout + result.stderr).lower()
    assert "doctor" in text
    assert "index" in text or "state" in text


def test_auto_runs_after_the_index_is_repaired(tmp_path: Path) -> None:
    repo(tmp_path)
    ghost_index(tmp_path)
    assert run_dispatch(tmp_path, "doctor", "--fix").returncode == 0

    result = run_dispatch(tmp_path, "auto", "01", "--executor", "python exec.py", "--until", "review")

    assert result.returncode == 0, result.stdout + result.stderr
