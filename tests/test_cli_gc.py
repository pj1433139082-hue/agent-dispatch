from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_dispatch(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=tmp_path, env=env, text=True, capture_output=True, check=False)


def git(tmp_path: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True, text=True).stdout.strip()


def make_ended_run(tmp_path: Path, name: str, *, dirty: bool, landed: bool) -> tuple[Path, str]:
    git(tmp_path, "init", "-q")
    (tmp_path / "keep.txt").write_text("x", encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")
    branch = "dispatch/" + name
    git(tmp_path, "branch", branch)
    worktree = tmp_path / ".dispatch" / "worktrees" / name
    worktree.parent.mkdir(parents=True, exist_ok=True)
    git(tmp_path, "worktree", "add", "-q", str(worktree), branch)
    if dirty:
        (worktree / "scratch.txt").write_text("wip", encoding="utf-8")
    run_dir = tmp_path / ".dispatch" / "runs" / name
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": name, "ticket_id": "01-" + name, "state": "done",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "use_worktree": True, "worktree_branch": branch,
        "execution_root": str(worktree.relative_to(tmp_path)),
    }), encoding="utf-8")
    if landed:
        (run_dir / "landing.json").write_text(json.dumps({"ticket_id": "01-" + name}), encoding="utf-8")
    state = tmp_path / ".dispatch" / "state.json"
    data = json.loads(state.read_text(encoding="utf-8")) if state.is_file() else {"version": 1, "tickets": {}}
    data["tickets"]["01-" + name] = {"run_id": name, "state": "done"}
    state.write_text(json.dumps(data), encoding="utf-8")
    return worktree, branch


def test_gc_marks_clean_landed_remove_and_dirty_hold(tmp_path: Path) -> None:
    clean_wt, clean_branch = make_ended_run(tmp_path, "clean-run", dirty=False, landed=True)
    dirty_wt, _ = make_ended_run(tmp_path, "dirty-run", dirty=True, landed=True)

    result = run_dispatch(tmp_path, "gc", "--json")

    assert result.returncode == 0, result.stderr
    rows = {row["ticket_id"]: row for row in json.loads(result.stdout)}
    assert rows["01-clean-run"]["verdict"] == "REMOVE"
    assert rows["01-dirty-run"]["verdict"] == "HOLD"
    assert clean_wt.is_dir() and dirty_wt.is_dir(), "dry run must not delete anything"


def test_gc_apply_removes_clean_worktree_and_keeps_dirty(tmp_path: Path) -> None:
    clean_wt, clean_branch = make_ended_run(tmp_path, "clean-run", dirty=False, landed=True)
    dirty_wt, _ = make_ended_run(tmp_path, "dirty-run", dirty=True, landed=True)

    result = run_dispatch(tmp_path, "gc", "--apply", "--json")

    assert result.returncode == 0, result.stderr
    assert not clean_wt.is_dir()
    assert dirty_wt.is_dir()
    branches = git(tmp_path, "branch", "--list").split()
    assert clean_branch not in branches
