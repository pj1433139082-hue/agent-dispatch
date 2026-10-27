from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: verify after landing

**What to build:** 写 docs/01.txt。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: docs/01.txt
- Verify: {verify}

## Acceptance

- [ ] docs/01.txt 存在。
"""

GOOD = '''python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('docs/01.txt').is_file() else 1)"'''
# 只在 worktree 里成立：executor 会写一个被 gitignore 的标记文件，合进分支后它不存在
BAD = '''python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('.verify-marker').exists() else 1)"'''

EXEC = """import json, os, pathlib
run = pathlib.Path(os.environ["DISPATCH_RUN_DIR"])
p = pathlib.Path("docs/01.txt")
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text("ok", encoding="utf-8")
pathlib.Path(".verify-marker").write_text("x", encoding="utf-8")
run.joinpath("receipt.json").write_text(json.dumps({
  "ticket_id": "01", "run_id": os.environ["DISPATCH_RUN_ID"], "status": "done", "summary": "ok",
  "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "file", "path": "docs/01.txt"}]}],
}), encoding="utf-8")
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def ready_repo(tmp_path: Path, verify: str) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET.format(verify=verify), encoding="utf-8")
    (tmp_path / ".dispatch").mkdir()
    (tmp_path / ".dispatch" / "config.json").write_text(
        json.dumps({"persona_policy": "off", "require_brief": False}), encoding="utf-8"
    )
    (tmp_path / "exec.py").write_text(EXEC, encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".dispatch/\n.verify-marker\n", encoding="utf-8")
    for args in (("init", "-q"), ("add", "-A"), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)
    assert run_dispatch(tmp_path, "auto", "01", "--executor", "python exec.py").returncode == 0
    assert run_dispatch(tmp_path, "review", "01", "--reviewer", "reviewer-b", "--verdict", "pass").returncode == 0


def test_land_verify_runs_the_ticket_commands_on_the_integration_branch(tmp_path: Path) -> None:
    ready_repo(tmp_path, GOOD)

    result = run_dispatch(tmp_path, "land", "01", "--verify")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "VERIFY-AFTER" in result.stdout
    assert "pass" in result.stdout.lower()


def test_land_verify_fails_when_the_branch_cannot_satisfy_the_commands(tmp_path: Path) -> None:
    ready_repo(tmp_path, BAD)

    result = run_dispatch(tmp_path, "land", "01", "--verify")

    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "VERIFY-AFTER" in combined
    assert "fail" in combined.lower()
