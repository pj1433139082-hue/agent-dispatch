from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: claim

## What to build

x

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: out.txt
- Write scope: src/**/*.py
- Verify: python -c "print(1)"

## Acceptance

- [ ] x
"""


def run_dispatch(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=tmp_path, env=env, text=True, capture_output=True, check=False)


def git(tmp_path: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)


def prepare(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")
    assert run_dispatch(tmp_path, "render", "01", "--no-worktree").returncode == 0


def test_claim_leases_the_write_scope(tmp_path: Path) -> None:
    prepare(tmp_path)

    result = run_dispatch(tmp_path, "claim", "01", "--json")

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert "out.txt" in report["granted"]
    assert "src/a.py" in report["granted"]
    assert report["conflicts"] == []
    assert (tmp_path / ".dispatch" / "locks" / "out.txt.json").is_file()


def test_second_run_cannot_claim_the_same_file(tmp_path: Path) -> None:
    prepare(tmp_path)
    assert run_dispatch(tmp_path, "claim", "01").returncode == 0
    first = json.loads((tmp_path / ".dispatch" / "locks" / "out.txt.json").read_text(encoding="utf-8"))

    # 伪造另一条 run 的租约请求：直接把锁文件的 run_id 换成别人，再看 claim 会不会让路
    first["run_id"] = "someone-else"
    (tmp_path / ".dispatch" / "locks" / "out.txt.json").write_text(json.dumps(first), encoding="utf-8")

    result = run_dispatch(tmp_path, "claim", "01", "--json")

    assert result.returncode == 3
    report = json.loads(result.stdout)
    assert any(item["path"] == "out.txt" for item in report["conflicts"])


def test_expired_lease_can_be_taken_over(tmp_path: Path) -> None:
    prepare(tmp_path)
    lock = tmp_path / ".dispatch" / "locks" / "out.txt.json"
    lock.parent.mkdir(parents=True, exist_ok=True)
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    lock.write_text(json.dumps({"path": "out.txt", "ticket_id": "other", "run_id": "someone-else", "expires_at": past}), encoding="utf-8")

    result = run_dispatch(tmp_path, "claim", "01", "--json")

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["conflicts"] == []
