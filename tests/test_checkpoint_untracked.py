from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def test_checkpoint_includes_untracked_files_in_the_patch(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(
        "# 01: cp\n\n## What to build\n\nx\n\n**Blocked by:** None\n**Status:** ready-for-agent\n\n"
        "## Dispatch\n\n- Owner: a\n- Risk: L1\n- Write scope: new.txt\n- Verify: python -c \"print(1)\"\n\n"
        "## Acceptance\n\n- [ ] x\n", encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)
    assert run_dispatch(tmp_path, "render", "01", "--agent", "lead").returncode == 0
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    worktree = Path(run["execution_root"])
    if not worktree.is_absolute():
        worktree = tmp_path / worktree
    (worktree / "new.txt").write_text("hello\n", encoding="utf-8")

    assert run_dispatch(tmp_path, "checkpoint", "01", "--label", "probe").returncode == 0

    patch = (run_dir / "checkpoints" / "001-probe" / "diff.patch").read_text(encoding="utf-8")
    assert "hello" in patch, patch
