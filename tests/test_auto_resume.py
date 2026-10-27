from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: resume

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
    "ticket_id": os.environ["DISPATCH_TICKET_ID"], "run_id": os.environ["DISPATCH_RUN_ID"],
    "status": "done", "summary": "ok",
    "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
}), encoding="utf-8")
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def test_auto_refuses_an_active_run_but_resume_continues_it(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    (tmp_path / "exec.py").write_text(EXECUTOR, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)
    assert run_dispatch(tmp_path, "render", "01", "--agent", "lead").returncode == 0
    assert run_dispatch(tmp_path, "start", "01").returncode == 0
    before = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0].name

    refused = run_dispatch(tmp_path, "auto", "01", "--executor", "python exec.py", "--force")
    assert refused.returncode != 0
    assert "--resume" in (refused.stdout + refused.stderr)

    resumed = run_dispatch(tmp_path, "auto", "01", "--executor", "python exec.py", "--force", "--resume")

    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    after = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0].name
    assert after == before
