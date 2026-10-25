from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: fix

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


def repo(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)


def test_wrap_fix_drops_expired_leases(tmp_path: Path) -> None:
    repo(tmp_path)
    locks = tmp_path / ".dispatch" / "locks"
    locks.mkdir(parents=True)
    expired = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    (locks / "out.txt.json").write_text(json.dumps({
        "path": "out.txt", "ticket_id": "01", "run_id": "r1", "expires_at": expired,
    }), encoding="utf-8")

    result = run_dispatch(tmp_path, "wrap", "--fix", "--json")

    payload = json.loads(result.stdout)
    assert payload["fix"]["released"] == ["out.txt"]
    assert not (locks / "out.txt.json").exists()


def test_wrap_fix_leaves_a_live_lease_alone(tmp_path: Path) -> None:
    repo(tmp_path)
    locks = tmp_path / ".dispatch" / "locks"
    locks.mkdir(parents=True)
    live = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    (locks / "out.txt.json").write_text(json.dumps({
        "path": "out.txt", "ticket_id": "01", "run_id": "r1", "expires_at": live,
    }), encoding="utf-8")

    result = run_dispatch(tmp_path, "wrap", "--fix", "--json")

    payload = json.loads(result.stdout)
    assert payload["fix"]["released"] == []
    assert (locks / "out.txt.json").exists()
