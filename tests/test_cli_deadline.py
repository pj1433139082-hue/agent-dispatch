from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: deadline

## What to build

x

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: out.txt
- Verify: python -c "print(1)"

## Acceptance

- [ ] x
"""


def run_dispatch(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "agent_dispatch", *args],
        cwd=tmp_path, env=env, text=True, capture_output=True, check=False,
    )


def git(tmp_path: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args],
        cwd=tmp_path, check=True, capture_output=True,
    )


def test_render_records_the_deadline(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")

    assert run_dispatch(tmp_path, "render", "01", "--no-worktree", "--deadline-minutes", "1").returncode == 0

    run = json.loads(sorted((tmp_path / ".dispatch" / "runs").iterdir())[0].joinpath("run.json").read_text(encoding="utf-8"))
    assert run["deadline_seconds"] == 60


def test_sweep_flags_a_run_past_its_deadline(tmp_path: Path) -> None:
    run_dir = tmp_path / ".dispatch" / "runs" / "01-late-20261022T000000Z-aaaaaa"
    run_dir.mkdir(parents=True)
    created = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    (run_dir / "run.json").write_text(
        json.dumps({"run_id": "01-late-20261022T000000Z-aaaaaa", "ticket_id": "01-late", "state": "running",
                    "created_at": created, "deadline_seconds": 900}),
        encoding="utf-8",
    )

    result = run_dispatch(tmp_path, "sweep", "--json")

    rows = json.loads(result.stdout)
    assert rows[0]["deadline_seconds"] == 900
    assert rows[0]["over_deadline"] is True
