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


def nested_root(tmp_path: Path) -> Path:
    inner = tmp_path / ".planning" / "recon" / "dispatch"
    (inner / "tickets").mkdir(parents=True)
    (inner / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    (inner / "config.json").write_text(json.dumps({"version": 1, "tickets_dir": "tickets"}), encoding="utf-8")
    return inner


def test_roots_finds_a_nested_dispatch_root(tmp_path: Path) -> None:
    nested_root(tmp_path)

    result = run_dispatch(tmp_path, "roots", "--json")

    payload = json.loads(result.stdout)
    assert len(payload["roots"]) == 1
    assert payload["roots"][0]["tickets"] == 1
    assert payload["roots"][0]["root"].endswith("dispatch") or payload["roots"][0]["root"].endswith("dispatch\\")


def test_wrap_points_at_other_roots_when_tickets_are_missing(tmp_path: Path) -> None:
    nested_root(tmp_path)

    result = run_dispatch(tmp_path, "wrap")

    assert result.returncode == 1
    assert "other dispatch root(s) found" in result.stdout
