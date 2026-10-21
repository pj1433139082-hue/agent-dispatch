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


def make_tickets(tmp_path: Path) -> Path:
    directory = tmp_path / "tickets"
    directory.mkdir()
    (directory / "01-a.md").write_text(ticket_text("01", "A"), encoding="utf-8")
    (directory / "02-b.md").write_text(ticket_text("02", "B", "01"), encoding="utf-8")
    return directory


def test_status_json_lists_every_ticket_and_frontier(tmp_path: Path) -> None:
    directory = make_tickets(tmp_path)

    result = run_dispatch(tmp_path, "status", "--tickets", str(directory), "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert [row["id"] for row in payload["tickets"]] == ["01", "02"]
    assert payload["frontier"] == ["01"]
    assert payload["tickets"][1]["state"] == "blocked"
    assert payload["tickets"][1]["blocked_by"] == ["01"]


def test_status_text_shows_every_ticket(tmp_path: Path) -> None:
    directory = make_tickets(tmp_path)

    result = run_dispatch(tmp_path, "status", "--tickets", str(directory))

    assert result.returncode == 0, result.stderr
    assert "01" in result.stdout
    assert "02" in result.stdout
    assert "Frontier" in result.stdout


def test_dsh_team_export_cli_is_valid_json(tmp_path: Path) -> None:
    directory = make_tickets(tmp_path)

    result = run_dispatch(tmp_path, "export", "--format", "dsh-team", "--tickets", str(directory))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload[0]["subject"] == "A"
    assert set(payload[0]) == {"subject", "description", "ownerName", "blockedBy", "writeScopes"}


def test_export_output_file_is_written(tmp_path: Path) -> None:
    directory = make_tickets(tmp_path)
    output = tmp_path / "export.md"

    result = run_dispatch(
        tmp_path,
        "export",
        "--format",
        "generic",
        "--tickets",
        str(directory),
        "--output",
        str(output),
    )

    assert result.returncode == 0, result.stderr
    assert "## 01: A" in output.read_text(encoding="utf-8")


def test_new_creates_a_lintable_ticket(tmp_path: Path) -> None:
    directory = tmp_path / "tickets"

    result = run_dispatch(
        tmp_path,
        "new",
        "03",
        "--title",
        "Third ticket",
        "--tickets",
        str(directory),
    )

    assert result.returncode == 0, result.stderr
    assert (directory / "03-third-ticket.md").is_file()
    lint = run_dispatch(tmp_path, "lint", "--tickets", str(directory))
    assert lint.returncode == 0, lint.stderr


def test_dsh_push_dry_run_is_json_and_does_not_need_a_server(tmp_path: Path) -> None:
    directory = make_tickets(tmp_path)

    result = run_dispatch(
        tmp_path,
        "dsh",
        "push",
        "--tickets",
        str(directory),
        "--root",
        str(tmp_path),
        "--project",
        "probe",
        "--dry-run",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["mode"] == "cards"
    assert payload["planned"][0]["ticket_id"] == "01"
    assert payload["planned"][0]["task_id"]
