from __future__ import annotations

import json
import subprocess
from pathlib import Path

from agent_dispatch.packet import build, render_markdown
from agent_dispatch.state import Run
from agent_dispatch.ticket import parse_ticket

TICKET = """# 04: Packet me

## What to build

Ship it.

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: src/app.py
- Verify: python -c "print(1)"

## Acceptance

- [ ] it works
"""


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args],
        cwd=repo, text=True, capture_output=True, check=True,
    ).stdout.strip()


def test_packet_freezes_ticket_diff_and_receipt(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "tickets").mkdir(parents=True)
    ticket_path = repo / "tickets" / "04.md"
    ticket_path.write_text(TICKET, encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("print(1)\n", encoding="utf-8")
    git(repo, "init", "-q")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    (repo / "src" / "app.py").write_text("print(2)\n", encoding="utf-8")

    run_dir = repo / ".dispatch" / "runs" / "R4"
    run_dir.mkdir(parents=True)
    data = {"run_id": "R4", "ticket_id": "04", "ticket_path": "tickets/04.md", "base_commit": base, "execution_root": str(repo)}
    (run_dir / "run.json").write_text(json.dumps(data), encoding="utf-8")
    (run_dir / "receipt.json").write_text(json.dumps({"ticket_id": "04", "status": "done"}), encoding="utf-8")
    (run_dir / "verify.json").write_text(json.dumps({"status": "passed"}), encoding="utf-8")

    report = build(repo, parse_ticket(ticket_path), Run(repo, run_dir, data))

    assert report["changed_files"] == ["src/app.py"]
    assert "print(2)" in report["diff"]
    assert len(report["hashes"]["diff"]) == 64
    assert report["hashes"]["ticket"] != report["hashes"]["receipt"]

    markdown = render_markdown(report)
    assert "# Review packet: 04 / R4" in markdown
    assert "src/app.py" in markdown
