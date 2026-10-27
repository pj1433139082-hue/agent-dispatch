from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: sub

## What to build

写报告。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: recon
- Risk: L1
- Write scope: reports/01.md
- Verify: python -c "print(1)"

## Acceptance

- [ ] 报告存在。
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def test_status_all_lists_nested_roots(tmp_path: Path) -> None:
    inner = tmp_path / ".planning" / "recon" / "dispatch"
    (inner / "tickets").mkdir(parents=True)
    (inner / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")

    result = run_dispatch(tmp_path, "status", "--all")

    assert result.returncode == 0
    assert "recon" in result.stdout
    assert "01" in result.stdout
