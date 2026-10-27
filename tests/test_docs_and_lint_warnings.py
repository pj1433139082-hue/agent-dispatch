from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: net

## What to build

写 out.txt。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: out.txt
- Verify: curl -s http://example.com | grep ok

## Acceptance

- [ ] out.txt 存在。
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def test_network_verify_is_a_warning_not_an_error(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")

    result = run_dispatch(tmp_path, "lint")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "WARN" in result.stderr
    assert "network_verify" in result.stderr
    assert "warning" in result.stdout


def test_requires_field_is_parsed_and_warned(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    text = TICKET.replace("- Risk: L1", "- Risk: L1\n- Requires: ssh")
    (tmp_path / "tickets" / "01.md").write_text(text, encoding="utf-8")

    result = run_dispatch(tmp_path, "lint")

    assert result.returncode == 0
    assert "environment_needed" in result.stderr


def test_invalid_requires_value_warns(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    text = TICKET.replace("- Risk: L1", "- Risk: L1\n- Requires: quantum")
    (tmp_path / "tickets" / "01.md").write_text(text, encoding="utf-8")

    result = run_dispatch(tmp_path, "lint")

    assert result.returncode == 0
    assert "invalid_requires" in result.stderr


def test_retry_requires_a_reason(tmp_path: Path) -> None:
    result = run_dispatch(tmp_path, "retry", "01")

    assert result.returncode == 2
    assert "--reason" in result.stderr


def test_commands_doc_matches_the_cli() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/gen_command_table.py", "--check"],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
