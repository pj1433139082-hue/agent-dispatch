from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: setup

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


def test_setup_writes_a_config_and_is_idempotent(tmp_path: Path) -> None:
    (tmp_path / "work" / "tickets").mkdir(parents=True)
    for args in (("init", "-q"),):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)

    first = run_dispatch(tmp_path, "setup", "--tickets", "work/tickets", "--executor-mode", "teammate", "--default-reviewer", "reviewer-b", "--json")
    assert first.returncode == 0, first.stdout + first.stderr
    config = json.loads((tmp_path / ".dispatch" / "config.json").read_text(encoding="utf-8"))
    assert config["tickets_dir"] == "work/tickets"
    assert config["executor_mode"] == "teammate"

    again = run_dispatch(tmp_path, "setup", "--json")
    assert again.returncode == 0
    kept = json.loads((tmp_path / ".dispatch" / "config.json").read_text(encoding="utf-8"))
    assert kept["tickets_dir"] == "work/tickets"


def test_lint_uses_the_configured_tickets_directory(tmp_path: Path) -> None:
    (tmp_path / "work" / "tickets").mkdir(parents=True)
    (tmp_path / "work" / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", "init", "-q"], cwd=tmp_path, check=True, capture_output=True)
    assert run_dispatch(tmp_path, "setup", "--tickets", "work/tickets").returncode == 0

    result = run_dispatch(tmp_path, "lint")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 ticket(s) valid" in result.stdout


def test_setup_refuses_a_missing_tickets_directory(tmp_path: Path) -> None:
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", "init", "-q"], cwd=tmp_path, check=True, capture_output=True)

    result = run_dispatch(tmp_path, "setup", "--tickets", "nope/tickets")

    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "nope" / "tickets").is_dir()
