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

EXECUTOR = """import json, os, pathlib
run = pathlib.Path(os.environ["DISPATCH_RUN_DIR"])
attempt = os.environ.get("DISPATCH_ATTEMPT", "1")
auto = run / "auto"
auto.mkdir(parents=True, exist_ok=True)
(auto / ("seen-" + attempt + ".txt")).write_text(os.environ.get("DISPATCH_FEEDBACK", ""), encoding="utf-8")
if attempt == "1":
    raise SystemExit(1)
pathlib.Path("out.txt").write_text("done", encoding="utf-8")
run.joinpath("receipt.json").write_text(json.dumps({
    "ticket_id": "01", "run_id": os.environ["DISPATCH_RUN_ID"], "status": "done", "summary": "done",
    "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
}), encoding="utf-8")
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def test_auto_feeds_previous_failure_into_the_next_attempt(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    (tmp_path / "exec.py").write_text(EXECUTOR, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)

    result = run_dispatch(tmp_path, "auto", "01", "--executor", "python exec.py", "--max-attempts", "2")

    assert result.returncode == 0, result.stdout + result.stderr
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    auto = json.loads((run_dir / "auto.json").read_text(encoding="utf-8"))
    assert len(auto["attempts"]) == 2, auto
    feedback = list((run_dir / "auto").glob("feedback-*.md"))
    assert feedback, "第一次失败应该留下 feedback 文件"
    assert "findings" in feedback[0].read_text(encoding="utf-8").lower()
    seen = (run_dir / "auto" / "seen-2.txt").read_text(encoding="utf-8")
    assert "feedback" in seen.lower(), repr(seen)


# Executor that is killed while running attempt 2: it records that it started,
# writes nothing, and exits non-zero. The retry must already be ledgered.
KILLING_EXECUTOR = """import os, pathlib, signal
run = pathlib.Path(os.environ["DISPATCH_RUN_DIR"])
attempt = os.environ.get("DISPATCH_ATTEMPT", "1")
auto = run / "auto"
auto.mkdir(parents=True, exist_ok=True)
(auto / ("started-" + attempt + ".txt")).write_text("started", encoding="utf-8")
if attempt == "1":
    raise SystemExit(1)
# Attempt 2 dies in flight: kill our own process group without finishing.
os.kill(os.getpid(), signal.SIGTERM)
"""


def ledger_rows(root: Path, ticket_id: str) -> list[dict[str, object]]:
    """Read retry-ledger rows for one ticket (both ledgers)."""
    rows: list[dict[str, object]] = []
    for name in ("retries.jsonl", "dropped.jsonl"):
        path = root / ".dispatch" / "ledger" / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and row.get("ticket_id") == ticket_id:
                rows.append(row)
    return rows


def test_retry_is_ledgered_before_the_attempt_runs(tmp_path: Path) -> None:
    """A crash during attempt 2 must still leave the retry recorded."""
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    (tmp_path / "exec.py").write_text(KILLING_EXECUTOR, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)

    run_dispatch(tmp_path, "auto", "01", "--executor", "python exec.py", "--max-attempts", "2")

    # The run fails, but the retry that started must be in the ledger already.
    rows = ledger_rows(tmp_path, "01")
    assert len(rows) == 1, rows
    assert "attempt" in str(rows[0].get("reason", "")).lower(), rows[0]
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    assert (run_dir / "auto" / "started-2.txt").is_file(), "第二次尝试应该真的开始了"


def test_first_attempt_is_not_ledgered_as_a_retry(tmp_path: Path) -> None:
    """max-attempts=1 consumes no retry budget at all."""
    passing = """import json, os, pathlib
run = pathlib.Path(os.environ["DISPATCH_RUN_DIR"])
pathlib.Path("out.txt").write_text("done", encoding="utf-8")
run.joinpath("receipt.json").write_text(json.dumps({
    "ticket_id": "01", "run_id": os.environ["DISPATCH_RUN_ID"], "status": "done", "summary": "done",
    "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
}), encoding="utf-8")
"""
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    (tmp_path / "exec.py").write_text(passing, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)

    result = run_dispatch(tmp_path, "auto", "01", "--executor", "python exec.py", "--max-attempts", "1")

    assert result.returncode == 0, result.stdout + result.stderr
    assert ledger_rows(tmp_path, "01") == [], "首次尝试不是重试，不该记账"


def test_completed_auto_run_matches_attempt_count(tmp_path: Path) -> None:
    """A run that finishes after two attempts ledgers exactly one retry (not two)."""
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    (tmp_path / "exec.py").write_text(EXECUTOR, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)

    result = run_dispatch(tmp_path, "auto", "01", "--executor", "python exec.py", "--max-attempts", "2")

    assert result.returncode == 0, result.stdout + result.stderr
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    auto = json.loads((run_dir / "auto.json").read_text(encoding="utf-8"))
    assert len(auto["attempts"]) == 2, auto
    rows = ledger_rows(tmp_path, "01")
    # Two attempts means exactly one retry; the pre-attempt ledger and the old
    # post-hoc loop must never both fire for the same attempt.
    assert len(rows) == 1, rows
