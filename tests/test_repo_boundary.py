from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: nested

## What to build

x

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


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def test_render_refuses_a_root_inside_another_repository(tmp_path: Path) -> None:
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", "init", "-q"], cwd=tmp_path, check=True)
    inner = tmp_path / "water"
    (inner / "tickets").mkdir(parents=True)
    (inner / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    (tmp_path / "seed.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", "commit", "-q", "-m", "base"], cwd=tmp_path, check=True)

    result = run_dispatch(inner, "render", "01")

    assert result.returncode != 0
    text = (result.stdout + result.stderr).lower()
    assert "another" in text or "nested" in text or "toplevel" in text
