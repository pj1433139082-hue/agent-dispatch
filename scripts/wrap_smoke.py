#!/usr/bin/env python3
"""Smoke-test `dispatch wrap` in two states: a healthy repo and a missing tickets dir."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: smoke

**What to build:** x
**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: out.txt
- Verify: python -c "print(1)"

## Acceptance

- [ ] x
"""


def run_wrap(cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "agent_dispatch", "wrap"],
        cwd=cwd, env=env, text=True, capture_output=True, check=False,
    )


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "healthy"
        (repo / "tickets").mkdir(parents=True)
        (repo / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
        (repo / ".dispatch").mkdir()
        (repo / ".dispatch" / "config.json").write_text(json.dumps({"persona_policy": "off"}), encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", "add", "-A"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", "commit", "-q", "-m", "base"], cwd=repo, check=True, capture_output=True)
        healthy = run_wrap(repo)
        if healthy.returncode != 0:
            failures.append("healthy repo: exit " + str(healthy.returncode) + "\n" + healthy.stdout + healthy.stderr)
        elif "CLEAN" not in healthy.stdout:
            failures.append("healthy repo: verdict is not CLEAN\n" + healthy.stdout)

        empty = Path(tmp) / "empty"
        empty.mkdir()
        missing = run_wrap(empty)
        if missing.returncode == 0:
            failures.append("missing tickets dir: expected non-zero exit")
        elif "tickets directory is missing" not in missing.stdout + missing.stderr:
            failures.append("missing tickets dir: expected a clear message\n" + missing.stdout + missing.stderr)

    if failures:
        print("WRAP SMOKE FAILED")
        for item in failures:
            print(" - " + item)
        return 1
    print("WRAP SMOKE OK: healthy=0 CLEAN, missing-tickets=1 with message")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
