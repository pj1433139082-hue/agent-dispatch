from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: weak

**What to build:** x
**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: a
- Risk: L1
- Write scope: out.txt
- Verify: {command}

## Acceptance

- [ ] x
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def lint_with(command: str, tmp_path: Path) -> str:
    (tmp_path / "tickets").mkdir(exist_ok=True)
    (tmp_path / "tickets" / "01.md").write_text(TICKET.format(command=command), encoding="utf-8")
    return run_dispatch(tmp_path, "lint").stderr


def test_trivially_true_verify_is_warned(tmp_path: Path) -> None:
    stderr = lint_with('python -c "print(1)"', tmp_path)
    assert "weak_verify" in stderr


def test_a_real_check_is_not_warned(tmp_path: Path) -> None:
    stderr = lint_with('python -c "import pathlib,sys; sys.exit(0 if pathlib.Path(\'out.txt\').exists() else 1)"', tmp_path)
    assert "weak_verify" not in stderr
