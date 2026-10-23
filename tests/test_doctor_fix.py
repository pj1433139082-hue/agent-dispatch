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


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def repo(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)


def write_lock(root: Path, expires_in_minutes: int) -> Path:
    directory = root / ".dispatch" / "locks"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "out.txt.json"
    expires = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)
    path.write_text(json.dumps({
        "path": "out.txt", "ticket_id": "01", "run_id": "01-x",
        "created_at": expires.isoformat(), "expires_at": expires.isoformat(),
    }), encoding="utf-8")
    return path


def test_fix_removes_expired_leases(tmp_path: Path) -> None:
    repo(tmp_path)
    lock = write_lock(tmp_path, -30)

    result = run_dispatch(tmp_path, "doctor", "--fix", "--json")

    payload = json.loads(result.stdout)
    assert not lock.exists()
    assert any("expired" in item.lower() for item in payload["fixed"])
    assert result.returncode == 0, payload


def test_fix_leaves_a_live_lease_alone(tmp_path: Path) -> None:
    repo(tmp_path)
    lock = write_lock(tmp_path, 30)

    result = run_dispatch(tmp_path, "doctor", "--fix")

    assert lock.exists()
    assert result.returncode == 0


def test_fix_rebuilds_a_stale_index(tmp_path: Path) -> None:
    repo(tmp_path)
    assert run_dispatch(tmp_path, "render", "01", "--no-worktree").returncode == 0
    state_path = tmp_path / ".dispatch" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["tickets"]["01"]["state"] = "failed"     # 索引被写歪，磁盘上是 claimed
    state_path.write_text(json.dumps(state), encoding="utf-8")

    fixed = run_dispatch(tmp_path, "doctor", "--fix", "--json")

    payload = json.loads(fixed.stdout)
    assert payload["fixed"], payload
    assert not any("retry" in issue for issue in payload["issues"])
