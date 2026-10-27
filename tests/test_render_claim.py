from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# {id}: lease

## What to build

写 out{id}.txt。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: shared.txt
- Verify: python -c "print(1)"

## Acceptance

- [ ] shared.txt 存在。
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def repo(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    for tid in ("01", "02"):
        (tmp_path / "tickets" / (tid + ".md")).write_text(TICKET.format(id=tid), encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)


def test_render_claim_takes_leases(tmp_path: Path) -> None:
    repo(tmp_path)

    result = run_dispatch(tmp_path, "render", "01", "--agent", "lead", "--claim")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Claimed" in result.stdout
    assert (tmp_path / ".dispatch" / "locks" / "shared.txt.json").is_file()


def test_second_render_claim_on_the_same_scope_is_blocked(tmp_path: Path) -> None:
    repo(tmp_path)
    assert run_dispatch(tmp_path, "render", "01", "--agent", "lead", "--claim").returncode == 0

    second = run_dispatch(tmp_path, "render", "02", "--agent", "lead", "--claim")

    assert second.returncode == 3
    assert "LEASE conflict" in second.stderr
    assert "shared.txt" in second.stderr
