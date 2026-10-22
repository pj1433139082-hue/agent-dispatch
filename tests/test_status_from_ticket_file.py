from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# {id}: {title}

## What to build

x

**Blocked by:** {blocked}
**Status:** {status}

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


def write(root: Path, tid: str, status: str, blocked: str = "None") -> None:
    (root / "tickets").mkdir(exist_ok=True)
    (root / "tickets" / (tid + ".md")).write_text(
        TICKET.format(id=tid, title=tid, blocked=blocked, status=status), encoding="utf-8"
    )


def test_a_ticket_marked_done_in_the_file_counts_as_done(tmp_path: Path) -> None:
    write(tmp_path, "01", "ready-for-agent")
    write(tmp_path, "02", "done")

    rows = json.loads(run_dispatch(tmp_path, "status", "--json").stdout)["tickets"]
    states = {row["id"]: row["state"] for row in rows}

    assert states["02"] == "done"


def test_a_done_ticket_unblocks_its_dependents(tmp_path: Path) -> None:
    write(tmp_path, "01", "done")
    write(tmp_path, "02", "ready-for-agent", blocked="01")

    payload = json.loads(run_dispatch(tmp_path, "status", "--json").stdout)

    assert payload["frontier"] == ["02"], payload
