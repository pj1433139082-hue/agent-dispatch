from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: x

**What to build:** x
**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: a
- Risk: L1
- Write scope: out.txt
- Verify: python -c "print(1)"

## Acceptance

- [ ] out.txt
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def test_missing_receipt_explains_the_stale_executor_trap(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    (tmp_path / ".dispatch").mkdir()
    (tmp_path / ".dispatch" / "config.json").write_text(json.dumps({"persona_policy": "off", "require_brief": False}), encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)
    assert run_dispatch(tmp_path, "render", "01", "--agent", "lead", "--no-worktree").returncode == 0
    run_dispatch(tmp_path, "start", "01")

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "receipt.json is missing" in combined
    assert "committed BEFORE render" in combined
