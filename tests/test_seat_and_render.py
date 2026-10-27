from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# {id}: seat

## What to build

写 out{id}.txt。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: out{id}.txt
- Verify: python -c "print(1)"

## Acceptance

- [ ] 某条。
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def repo(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    for tid in ("01", "02", "03"):
        (tmp_path / "tickets" / (tid + ".md")).write_text(TICKET.format(id=tid), encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)


def test_render_refuses_when_the_agent_is_at_its_seat_cap(tmp_path: Path) -> None:
    repo(tmp_path)
    assert run_dispatch(tmp_path, "render", "01", "--agent", "lead", "--seat-cap", "1").returncode == 0

    second = run_dispatch(tmp_path, "render", "02", "--agent", "lead", "--seat-cap", "1")

    assert second.returncode == 5
    assert "SEAT full" in second.stderr


def test_seat_counts_the_agents_real_active_tickets(tmp_path: Path) -> None:
    repo(tmp_path)
    assert run_dispatch(tmp_path, "render", "01", "--agent", "lead").returncode == 0

    result = run_dispatch(tmp_path, "seat", "--agent", "lead", "--cap", "2", "--json")

    payload = json.loads(result.stdout)
    assert payload["occupied"] == 1
    assert payload["free"] == 1
