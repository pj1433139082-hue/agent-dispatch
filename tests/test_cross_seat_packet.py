from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: cross

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

RECEIPT = """{"ticket_id": "01", "run_id": "__RUN__", "status": "done", "summary": "ok", "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}]}"""


def run_dispatch(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "agent_dispatch", *args],
        cwd=tmp_path, env=env, text=True, capture_output=True, check=False,
    )


def test_seat_verdicts(tmp_path: Path) -> None:
    ok = json.loads(run_dispatch(tmp_path, "seat", "--cap", "2", "--occupied", "1", "--json").stdout)
    assert ok["free"] == 1 and ok["verdict"] == "ok"

    reclaim = json.loads(
        run_dispatch(tmp_path, "seat", "--cap", "2", "--occupied", "2", "--inactive", "a,b", "--json").stdout
    )
    assert reclaim["verdict"] == "reclaim" and reclaim["inactive"] == ["a", "b"]

    blocked = json.loads(run_dispatch(tmp_path, "seat", "--cap", "2", "--occupied", "2", "--json").stdout)
    assert blocked["verdict"] == "blocked"


def test_review_packet_freezes_the_run(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", "commit", "-q", "-m", "base"], cwd=tmp_path, check=True)
    assert run_dispatch(tmp_path, "render", "01", "--no-worktree").returncode == 0
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    run_id = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))["run_id"]
    (tmp_path / "out.txt").write_text("x", encoding="utf-8")
    (run_dir / "receipt.json").write_text(RECEIPT.replace("__RUN__", run_id), encoding="utf-8")
    assert run_dispatch(tmp_path, "start", "01").returncode == 0
    assert run_dispatch(tmp_path, "verify", "01").returncode == 0, "verify should pass"

    result = run_dispatch(tmp_path, "review-packet", "01", "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    packet = tmp_path / payload["path"]
    assert packet.is_file()
    assert payload["hashes"]
