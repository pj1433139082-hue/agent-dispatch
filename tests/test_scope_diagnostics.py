from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: scope

## What to build

x

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: {scope}
- Verify: python -c "print(1)"

## Acceptance

- [ ] x
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def write_ticket(root: Path, scope: str) -> None:
    (root / "tickets").mkdir(exist_ok=True)
    (root / "tickets" / "01.md").write_text(TICKET.format(scope=scope), encoding="utf-8")


def test_absolute_scope_inside_the_project_suggests_the_relative_path(tmp_path: Path) -> None:
    write_ticket(tmp_path, (tmp_path / "data" / "x.parquet").as_posix())

    result = run_dispatch(tmp_path, "lint")

    assert result.returncode != 0
    text = result.stdout + result.stderr
    assert "data/x.parquet" in text.replace("\\", "/"), text


def test_absolute_scope_outside_the_project_says_so(tmp_path: Path) -> None:
    write_ticket(tmp_path, "D:/somewhere/else/x.parquet")

    result = run_dispatch(tmp_path, "lint")

    assert result.returncode != 0
    assert "outside" in (result.stdout + result.stderr).lower()


def test_a_relative_scope_still_passes(tmp_path: Path) -> None:
    write_ticket(tmp_path, "data/x.parquet")

    assert run_dispatch(tmp_path, "lint").returncode == 0
