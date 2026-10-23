from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: host package

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


def prepare(tmp_path: Path) -> tuple[Path, Path]:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)
    assert run_dispatch(tmp_path, "render", "01", "--agent", "lead").returncode == 0
    assert run_dispatch(tmp_path, "start", "01").returncode == 0
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    worktree = Path(run["execution_root"])
    if not worktree.is_absolute():
        worktree = tmp_path / worktree
    (worktree / "out.txt").write_text("ok", encoding="utf-8")
    package = worktree / ".agents" / "skills" / "some-skill"
    package.mkdir(parents=True)
    (package / "SKILL.md").write_text("# skill", encoding="utf-8")
    (run_dir / "receipt.json").write_text(json.dumps({
        "ticket_id": "01", "run_id": run["run_id"], "status": "done", "summary": "ok",
        "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
    }), encoding="utf-8")
    return run_dir, worktree


def test_out_of_scope_host_packages_get_a_hint(tmp_path: Path) -> None:
    prepare(tmp_path)

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode != 0
    text = (result.stdout + result.stderr).lower()
    assert "out of scope" in text
    assert "host" in text or "宿主" in text
