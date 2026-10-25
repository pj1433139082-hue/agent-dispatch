from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: persona

## What to build

写 out.txt。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: {risk}
- Write scope: out.txt
- Verify: python -c "print(1)"

## Acceptance

- [ ] out.txt 存在。
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def repo(tmp_path: Path, risk: str = "L2", policy: str = "l2") -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET.format(risk=risk), encoding="utf-8")
    (tmp_path / ".dispatch").mkdir(exist_ok=True)
    (tmp_path / ".dispatch" / "config.json").write_text(json.dumps({"persona_policy": policy}), encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)


def test_l2_without_a_persona_is_refused(tmp_path: Path) -> None:
    repo(tmp_path, "L2")

    result = run_dispatch(tmp_path, "render", "01", "--agent", "lead")

    assert result.returncode == 6
    assert "needs a persona" in result.stderr
    assert "dispatch assign 01" in result.stderr


def test_l1_without_a_persona_is_fine(tmp_path: Path) -> None:
    repo(tmp_path, "L1")

    assert run_dispatch(tmp_path, "render", "01", "--agent", "lead").returncode == 0


def test_policy_off_allows_l2_without_a_persona(tmp_path: Path) -> None:
    repo(tmp_path, "L2", policy="off")

    assert run_dispatch(tmp_path, "render", "01", "--agent", "lead").returncode == 0
