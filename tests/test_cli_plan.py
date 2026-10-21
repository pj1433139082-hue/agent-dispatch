from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ticket_text(ticket_id: str, title: str, blocked_by: str = "None") -> str:
    return f"""# {ticket_id}: {title}

**What to build:** Ship {title}.
**Blocked by:** {blocked_by}
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: src/{ticket_id}.py
- Verify: python -m pytest -q

## Acceptance

- [ ] {title} works.
"""


def run_dispatch(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "agent_dispatch", *args],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def write_tickets(tmp_path: Path) -> Path:
    directory = tmp_path / "tickets"
    directory.mkdir()
    (directory / "01-a.md").write_text(ticket_text("01", "A"), encoding="utf-8")
    (directory / "02-b.md").write_text(ticket_text("02", "B", "01"), encoding="utf-8")
    return directory


def test_plan_json_reports_waves_frontier_blocked_and_conflicts(tmp_path: Path) -> None:
    directory = write_tickets(tmp_path)

    result = run_dispatch(tmp_path, "plan", "--tickets", str(directory), "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["waves"] == [["01"], ["02"]]
    assert payload["frontier"] == ["01"]
    assert payload["blocked"] == {"02": ["01"]}
    assert payload["conflicts"] == []


def test_plan_json_marks_done_dependencies_as_satisfied(tmp_path: Path) -> None:
    directory = write_tickets(tmp_path)

    result = run_dispatch(
        tmp_path, "plan", "--tickets", str(directory), "--done", "01", "--json"
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["waves"] == [["02"]]
    assert payload["frontier"] == ["02"]


def test_plan_fails_on_lint_errors(tmp_path: Path) -> None:
    directory = tmp_path / "tickets"
    directory.mkdir()
    broken = ticket_text("01", "Broken").replace("- Owner: implementer\n", "")
    (directory / "01-broken.md").write_text(broken, encoding="utf-8")

    result = run_dispatch(tmp_path, "plan", "--tickets", str(directory), "--json")

    assert result.returncode == 1
    assert "missing_owner" in result.stderr
    assert result.stdout == ""
