from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# {tid}: wave append

**What to build:** 写 docs/{tid}.txt。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: docs/{tid}.txt
- Verify: python -c "import pathlib,sys; p=pathlib.Path('docs/{tid}.txt'); sys.exit(0 if p.is_file() else 1)"

## Acceptance

- [ ] docs/{tid}.txt 存在。
"""

EXEC = """import json, os, pathlib
tid = os.environ["DISPATCH_TICKET_ID"]
run = pathlib.Path(os.environ["DISPATCH_RUN_DIR"])
p = pathlib.Path("docs") / (tid + ".txt")
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(tid, encoding="utf-8")
run.joinpath("receipt.json").write_text(json.dumps({
  "ticket_id": tid, "run_id": os.environ["DISPATCH_RUN_ID"], "status": "done", "summary": "ok",
  "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "file", "path": str(p)}]}],
}), encoding="utf-8")
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def test_land_append_builds_one_cumulative_branch(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    for tid in ("01", "02"):
        (tmp_path / "tickets" / (tid + ".md")).write_text(TICKET.format(tid=tid), encoding="utf-8")
    (tmp_path / ".dispatch").mkdir()
    (tmp_path / ".dispatch" / "config.json").write_text(
        json.dumps({"persona_policy": "off", "require_brief": False}), encoding="utf-8"
    )
    (tmp_path / "exec.py").write_text(EXEC, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)

    for tid in ("01", "02"):
        assert run_dispatch(tmp_path, "auto", tid, "--executor", "python exec.py").returncode == 0
        assert run_dispatch(tmp_path, "review", tid, "--reviewer", "wave-reviewer", "--verdict", "pass").returncode == 0

    assert run_dispatch(tmp_path, "land", "01", "--branch", "wave/all").returncode == 0
    second = run_dispatch(tmp_path, "land", "02", "--branch", "wave/all", "--append")
    assert second.returncode == 0, second.stdout + second.stderr

    files = subprocess.run(["git", "ls-tree", "-r", "--name-only", "wave/all"], cwd=tmp_path, text=True, capture_output=True, check=True).stdout
    assert "docs/01.txt" in files and "docs/02.txt" in files
