from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# {id}: wave

## What to build

写 {id}.txt。

**Blocked by:** {blocked}
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: {id}.txt
- Verify: python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('{id}.txt').exists() else 1)"

## Acceptance

- [ ] {id}.txt 存在。
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=cwd, check=True, capture_output=True)


def make_repo(tmp_path: Path, tickets: list[tuple[str, str]]) -> None:
    (tmp_path / "tickets").mkdir()
    for tid, blocked in tickets:
        (tmp_path / "tickets" / (tid + ".md")).write_text(TICKET.format(id=tid, blocked=blocked), encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")


def drive_to_done(tmp_path: Path, tid: str) -> None:
    assert run_dispatch(tmp_path, "render", tid, "--agent", "lead").returncode == 0
    assert run_dispatch(tmp_path, "start", tid).returncode == 0
    run_dir = [p for p in (tmp_path / ".dispatch" / "runs").iterdir() if p.name.startswith(tid)][0]
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    worktree = Path(run["execution_root"])
    if not worktree.is_absolute():
        worktree = tmp_path / worktree
    (worktree / (tid + ".txt")).write_text("ok", encoding="utf-8")
    (run_dir / "receipt.json").write_text(json.dumps({
        "ticket_id": tid, "run_id": run["run_id"], "status": "done", "summary": "ok",
        "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
    }), encoding="utf-8")
    assert run_dispatch(tmp_path, "verify", tid).returncode == 0
    assert run_dispatch(tmp_path, "review", tid, "--reviewer", "reviewer-b", "--verdict", "pass").returncode == 0
    assert run_dispatch(tmp_path, "review-packet", tid).returncode == 0


def test_wave_lands_independent_tickets_in_one_command(tmp_path: Path) -> None:
    make_repo(tmp_path, [("01", "None"), ("02", "None")])
    drive_to_done(tmp_path, "01")
    drive_to_done(tmp_path, "02")

    result = run_dispatch(tmp_path, "land", "--wave", "--json")

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert sorted(item["ticket_id"] for item in payload["landed"]) == ["01", "02"]


def test_wave_lands_dependencies_before_dependents(tmp_path: Path) -> None:
    # 依赖方的 id 排在前面（a-blocked < z-base），只有拓扑排序才会先合 z-base
    make_repo(tmp_path, [("z-base", "None"), ("a-blocked", "z-base")])
    drive_to_done(tmp_path, "z-base")
    drive_to_done(tmp_path, "a-blocked")

    result = run_dispatch(tmp_path, "land", "--wave", "--json")

    assert result.returncode == 0, result.stdout + result.stderr
    landed = [item["ticket_id"] for item in json.loads(result.stdout)["landed"]]
    assert landed == ["z-base", "a-blocked"], landed


def test_wave_reports_what_it_skipped(tmp_path: Path) -> None:
    make_repo(tmp_path, [("z-base", "None"), ("a-blocked", "z-base")])
    drive_to_done(tmp_path, "z-base")

    result = run_dispatch(tmp_path, "land", "--wave", "--json")

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert [item["ticket_id"] for item in payload["landed"]] == ["z-base"]
    reasons = {item["ticket_id"]: item["reason"] for item in payload["skipped"]}
    assert reasons["a-blocked"] == "not done"


def test_wave_is_idempotent(tmp_path: Path) -> None:
    make_repo(tmp_path, [("01", "None")])
    drive_to_done(tmp_path, "01")
    assert run_dispatch(tmp_path, "land", "--wave").returncode == 0

    again = run_dispatch(tmp_path, "land", "--wave", "--json")

    payload = json.loads(again.stdout)
    assert payload["landed"] == []
    assert payload["skipped"][0]["reason"] == "already landed"
