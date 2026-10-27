from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: lease

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


def test_claim_renews_its_own_lease(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)
    assert run_dispatch(tmp_path, "render", "01", "--agent", "lead").returncode == 0
    assert run_dispatch(tmp_path, "claim", "01", "--ttl-minutes", "1").returncode == 0
    lock = tmp_path / ".dispatch" / "locks" / "out.txt.json"
    first = json.loads(lock.read_text(encoding="utf-8"))["expires_at"]

    assert run_dispatch(tmp_path, "claim", "01", "--ttl-minutes", "30").returncode == 0

    second = json.loads(lock.read_text(encoding="utf-8"))["expires_at"]
    assert second > first, (first, second)


def test_release_without_a_run_is_a_no_op(tmp_path: Path) -> None:
    result = run_dispatch(tmp_path, "release", "01")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Released 0 lease(s)" in result.stdout
