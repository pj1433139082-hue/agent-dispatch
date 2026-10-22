from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: placeholder

## What to build

x

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: {scope}
- Verify: {verify}

## Acceptance

- [ ] x
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def write_ticket(root: Path, scope: str, verify: str) -> None:
    (root / "tickets").mkdir(exist_ok=True)
    (root / "tickets" / "01.md").write_text(TICKET.format(scope=scope, verify=verify), encoding="utf-8")


def test_lint_rejects_placeholder_write_scope(tmp_path: Path) -> None:
    write_ticket(tmp_path, "（待填）", "python -c \"print(1)\"")

    result = run_dispatch(tmp_path, "lint")

    assert result.returncode != 0
    assert "placeholder" in (result.stdout + result.stderr).lower()


def test_lint_rejects_placeholder_verify(tmp_path: Path) -> None:
    write_ticket(tmp_path, "out.txt", "（待填，必须可复跑）")

    result = run_dispatch(tmp_path, "lint")

    assert result.returncode != 0
    assert "placeholder" in (result.stdout + result.stderr).lower()


def test_lint_accepts_a_filled_ticket(tmp_path: Path) -> None:
    write_ticket(tmp_path, "out.txt", "python -c \"print(1)\"")

    result = run_dispatch(tmp_path, "lint")

    assert result.returncode == 0, result.stdout + result.stderr
