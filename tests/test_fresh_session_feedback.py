from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: polish

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


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=cwd, check=True, capture_output=True)


def repo(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")


def test_setup_writes_a_gitignore_for_dispatch_state(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    git(tmp_path, "init", "-q")

    assert run_dispatch(tmp_path, "setup").returncode == 0

    ignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert ".dispatch/" in ignore


def test_land_lists_the_dirty_paths(tmp_path: Path) -> None:
    repo(tmp_path)
    assert run_dispatch(tmp_path, "render", "01", "--agent", "lead").returncode == 0
    assert run_dispatch(tmp_path, "start", "01").returncode == 0
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    worktree = Path(run["execution_root"])
    if not worktree.is_absolute():
        worktree = tmp_path / worktree
    (worktree / "out.txt").write_text("ok", encoding="utf-8")
    (run_dir / "receipt.json").write_text(json.dumps({
        "ticket_id": "01", "run_id": run["run_id"], "status": "done", "summary": "ok",
        "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
    }), encoding="utf-8")
    assert run_dispatch(tmp_path, "verify", "01").returncode == 0
    assert run_dispatch(tmp_path, "review", "01", "--reviewer", "reviewer-b", "--verdict", "pass").returncode == 0
    (tmp_path / "stray.txt").write_text("dirty", encoding="utf-8")

    result = run_dispatch(tmp_path, "land", "01")

    assert result.returncode != 0
    assert "stray.txt" in (result.stdout + result.stderr)


def test_review_falls_back_to_the_configured_default_reviewer(tmp_path: Path) -> None:
    repo(tmp_path)
    assert run_dispatch(tmp_path, "setup", "--default-reviewer", "reviewer-config").returncode == 0
    assert run_dispatch(tmp_path, "render", "01", "--no-worktree").returncode == 0
    assert run_dispatch(tmp_path, "start", "01").returncode == 0
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    (tmp_path / "out.txt").write_text("ok", encoding="utf-8")
    (run_dir / "receipt.json").write_text(json.dumps({
        "ticket_id": "01", "run_id": run["run_id"], "status": "done", "summary": "ok",
        "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
    }), encoding="utf-8")
    assert run_dispatch(tmp_path, "verify", "01").returncode == 0

    result = run_dispatch(tmp_path, "review", "01", "--verdict", "pass")

    assert result.returncode == 0, result.stdout + result.stderr
    review = json.loads((run_dir / "review.json").read_text(encoding="utf-8"))
    assert review["reviewer"] == "reviewer-config"


def test_new_generates_a_real_acceptance_line(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    git(tmp_path, "init", "-q")

    assert run_dispatch(
        tmp_path, "new", "01", "--title", "hello", "--what", "创建 hello.txt",
        "--write-scope", "hello.txt", "--verify", 'python -c "print(1)"',
    ).returncode == 0

    text = (tmp_path / "tickets" / "01-hello.md").read_text(encoding="utf-8")
    assert "- [ ] 创建 hello.txt" in text
    assert "is complete" not in text


def test_verify_prints_where_the_record_lives(tmp_path: Path) -> None:
    repo(tmp_path)
    assert run_dispatch(tmp_path, "render", "01", "--no-worktree").returncode == 0
    assert run_dispatch(tmp_path, "start", "01").returncode == 0
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    (tmp_path / "out.txt").write_text("ok", encoding="utf-8")
    (run_dir / "receipt.json").write_text(json.dumps({
        "ticket_id": "01", "run_id": run["run_id"], "status": "done", "summary": "ok",
        "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
    }), encoding="utf-8")

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode == 0
    assert "verify.json" in result.stdout
