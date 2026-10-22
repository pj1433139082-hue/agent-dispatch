from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# {id}: race

## What to build

x

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: shared.txt
- Verify: python -c "print(1)"

## Acceptance

- [ ] x
"""


def env() -> dict[str, str]:
    value = os.environ.copy()
    value["PYTHONPATH"] = str(ROOT / "src")
    return value


def test_two_processes_cannot_claim_the_same_file(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET.format(id="01"), encoding="utf-8")
    (tmp_path / "tickets" / "02.md").write_text(TICKET.format(id="02"), encoding="utf-8")
    (tmp_path / "shared.txt").write_text("x", encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)
    for ticket in ("01", "02"):
        assert subprocess.run([sys.executable, "-m", "agent_dispatch", "render", ticket, "--no-worktree"], cwd=tmp_path, env=env(), capture_output=True).returncode == 0

    first = subprocess.Popen([sys.executable, "-m", "agent_dispatch", "claim", "01"], cwd=tmp_path, env=env(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    second = subprocess.Popen([sys.executable, "-m", "agent_dispatch", "claim", "02"], cwd=tmp_path, env=env(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    codes = sorted([first.wait(timeout=60), second.wait(timeout=60)])

    assert codes == [0, 3], (codes, first.stderr.read() if first.stderr else "", second.stderr.read() if second.stderr else "")
    locks = list((tmp_path / ".dispatch" / "locks").glob("*.json"))
    assert len(locks) == 1
    owner = json.loads(locks[0].read_text(encoding="utf-8"))["ticket_id"]
    assert owner in {"01", "02"}
