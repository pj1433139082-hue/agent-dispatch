from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: retry

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


def start_failed_run(tmp_path: Path) -> Path:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)
    assert run_dispatch(tmp_path, "render", "01", "--agent", "lead").returncode == 0
    assert run_dispatch(tmp_path, "start", "01").returncode == 0
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    (run_dir / "receipt.json").write_text(json.dumps({
        "ticket_id": "01", "run_id": run["run_id"], "status": "done", "summary": "half",
        "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
    }), encoding="utf-8")
    failed = run_dispatch(tmp_path, "verify", "01")
    assert failed.returncode != 0, failed.stdout
    return run_dir


def test_retry_puts_a_failed_ticket_back_to_running(tmp_path: Path) -> None:
    run_dir = start_failed_run(tmp_path)

    retried = run_dispatch(tmp_path, "retry", "01", "--reason", "probe", "--reason", "补上缺失文件后重跑")
    assert retried.returncode == 0, retried.stdout + retried.stderr

    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert run["state"] == "running"
    state = json.loads((tmp_path / ".dispatch" / "state.json").read_text(encoding="utf-8"))
    assert state["tickets"]["01"]["state"] == "running"

    worktree = Path(run["execution_root"])
    if not worktree.is_absolute():
        worktree = tmp_path / worktree
    (worktree / "out.txt").write_text("ok", encoding="utf-8")
    (run_dir / "receipt.json").write_text(json.dumps({
        "ticket_id": "01", "run_id": run["run_id"], "status": "done", "summary": "done",
        "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
    }), encoding="utf-8")
    assert run_dispatch(tmp_path, "verify", "01").returncode == 0


def test_retry_keeps_the_previous_verdict_for_audit(tmp_path: Path) -> None:
    run_dir = start_failed_run(tmp_path)

    assert run_dispatch(tmp_path, "retry", "01", "--reason", "probe", "--reason", "second attempt").returncode == 0

    attempts = sorted((run_dir / "attempts").glob("verify-*.json"))
    assert attempts, "上一次的 verify.json 应该被归档"


def test_retry_refuses_a_done_ticket(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)
    state = {"version": 1, "tickets": {"01": {"run_id": "x", "state": "done", "updated_at": "2026-10-23T00:00:00+00:00"}}}
    (tmp_path / ".dispatch").mkdir()
    (tmp_path / ".dispatch" / "state.json").write_text(json.dumps(state), encoding="utf-8")

    result = run_dispatch(tmp_path, "retry", "01", "--reason", "probe")

    assert result.returncode != 0
    assert "done" in (result.stdout + result.stderr).lower()


def test_budget_survives_rerender_and_archive(tmp_path: Path) -> None:
    start_failed_run(tmp_path)
    # A failed run can be replaced repeatedly; each replacement consumes a retry.
    for _ in range(2):
        result = run_dispatch(tmp_path, "render", "01", "--agent", "lead")
        assert result.returncode == 0, result.stderr
        assert run_dispatch(tmp_path, "start", "01").returncode == 0
        assert run_dispatch(tmp_path, "verify", "01").returncode != 0
    dropped = run_dispatch(tmp_path, "drop", "01", "--reason", "reopen")
    assert dropped.returncode == 0, dropped.stderr
    denied = run_dispatch(tmp_path, "render", "01", "--agent", "lead")
    assert denied.returncode != 0
    assert "human evaluation" in denied.stderr
    assert "--override-limit" not in denied.stderr
    missing = run_dispatch(tmp_path, "render", "01", "--override-limit")
    assert missing.returncode != 0
    allowed = run_dispatch(tmp_path, "render", "01", "--agent", "lead", "--override-limit", "--reason", "tool outage")
    assert allowed.returncode == 0, allowed.stderr
    ledger = tmp_path / ".dispatch" / "ledger" / "retries.jsonl"
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert [row["override"] for row in rows] == [False, False, True]
    assert rows[-1]["reason"] == "tool outage"


def test_retry_budget_and_override(tmp_path: Path) -> None:
    start_failed_run(tmp_path)
    for _ in range(3):
        assert run_dispatch(tmp_path, "retry", "01", "--reason", "failure").returncode == 0
        assert run_dispatch(tmp_path, "verify", "01").returncode != 0
    denied = run_dispatch(tmp_path, "retry", "01", "--reason", "again")
    assert denied.returncode != 0 and "human evaluation" in denied.stderr
    assert "--override-limit" not in denied.stderr
    auto = run_dispatch(tmp_path, "auto", "01", "--executor", "unused", "--resume")
    assert auto.returncode != 0 and "human evaluation" in auto.stderr
    assert run_dispatch(tmp_path, "retry", "01", "--reason", " ", "--override-limit").returncode != 0
    assert run_dispatch(tmp_path, "retry", "01", "--reason", "external failure", "--override-limit").returncode == 0


def test_auto_attempts_consume_budget_and_exhaustion_blocks_resume(tmp_path: Path) -> None:
    start_failed_run(tmp_path)
    result = run_dispatch(tmp_path, "auto", "01", "--executor", "python -c pass", "--max-attempts", "10", "--json")
    assert result.returncode != 0
    data = json.loads(result.stdout)
    # One unit replaces the failed run; two more pay for attempts 2 and 3.
    assert len(data["attempts"]) == 3
    ledger = tmp_path / ".dispatch" / "ledger" / "retries.jsonl"
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 3
    assert all(not row["override"] for row in rows)
    denied = run_dispatch(tmp_path, "auto", "01", "--executor", "python -c pass", "--max-attempts", "2", "--resume")
    assert denied.returncode != 0 and "human evaluation" in denied.stderr
    assert "--override-limit" not in denied.stderr
    missing = run_dispatch(tmp_path, "auto", "01", "--executor", "python -c pass", "--override-limit", "--reason", " ")
    assert missing.returncode != 0
    override = run_dispatch(tmp_path, "auto", "01", "--executor", "python -c pass", "--max-attempts", "2", "--override-limit", "--reason", "tool outage", "--json")
    assert override.returncode != 0
    assert len(json.loads(override.stdout)["attempts"]) == 2
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 5
    assert all(row["override"] and row["reason"] == "tool outage" for row in rows[-2:])
