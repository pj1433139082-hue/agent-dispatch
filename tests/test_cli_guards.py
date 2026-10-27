from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: guards

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


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=cwd, check=True, capture_output=True)


def prepare(tmp_path: Path) -> Path:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")
    assert run_dispatch(tmp_path, "render", "01", "--agent", "lead").returncode == 0
    assert run_dispatch(tmp_path, "start", "01").returncode == 0
    return sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]


def test_closeout_refuses_a_run_without_evidence(tmp_path: Path) -> None:
    run_dir = prepare(tmp_path)

    result = run_dispatch(tmp_path, "closeout", "01")

    assert result.returncode != 0
    report = json.loads((run_dir / "closeout.json").read_text(encoding="utf-8"))
    assert report["status"] != "pass"
    assert report["findings"]


def test_land_can_require_a_passing_closeout(tmp_path: Path) -> None:
    prepare(tmp_path)

    result = run_dispatch(tmp_path, "land", "01", "--require-closeout")

    assert result.returncode != 0
    assert "closeout" in (result.stdout + result.stderr).lower()


def test_checkpoint_publishes_and_lists_a_generation(tmp_path: Path) -> None:
    run_dir = prepare(tmp_path)

    created = run_dispatch(tmp_path, "checkpoint", "01", "--label", "before-review")
    assert created.returncode == 0, created.stderr
    (run_dir / "current.json").is_file()

    listed = run_dispatch(tmp_path, "checkpoint", "01", "--list", "--json")
    assert listed.returncode == 0, listed.stderr
    generations = json.loads(listed.stdout)
    assert generations and generations[-1]["label"] == "before-review"


def test_land_releases_the_claimed_files(tmp_path: Path) -> None:
    run_dir = prepare(tmp_path)
    assert run_dispatch(tmp_path, "claim", "01").returncode == 0
    assert list((tmp_path / ".dispatch" / "locks").glob("*.json"))

    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    worktree = Path(run["execution_root"])
    if not worktree.is_absolute():
        worktree = tmp_path / worktree
    (worktree / "out.txt").write_text("x", encoding="utf-8")
    (run_dir / "receipt.json").write_text(json.dumps({
        "ticket_id": "01", "run_id": run["run_id"], "status": "done", "summary": "ok",
        "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
    }), encoding="utf-8")
    assert run_dispatch(tmp_path, "verify", "01").returncode == 0
    assert run_dispatch(tmp_path, "review", "01", "--reviewer", "reviewer-b", "--verdict", "pass").returncode == 0

    landed = run_dispatch(tmp_path, "land", "01")

    assert landed.returncode == 0, landed.stderr
    assert list((tmp_path / ".dispatch" / "locks").glob("*.json")) == []
