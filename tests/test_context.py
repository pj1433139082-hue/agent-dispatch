from __future__ import annotations

import json
from pathlib import Path

from agent_dispatch.context import build_context_pack, context_path, write_context_pack
from agent_dispatch.ticket import parse_ticket


TICKET = """# 07: Add the widget

**What to build:** A widget that survives reloads.
**Blocked by:** 06
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: src/widget.py
- Read scope: docs/widget.md
- Verify: python -m pytest tests/test_widget.py -q

## Acceptance

- [ ] The widget survives a reload.
"""


def make_repo(tmp_path: Path) -> Path:
    (tmp_path / "tickets").mkdir()
    ticket_path = tmp_path / "tickets" / "07-widget.md"
    ticket_path.write_text(TICKET, encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("# Agents\n\nRead CONTEXT.md first.\n", encoding="utf-8")
    (tmp_path / "CONTEXT.md").write_text("# Context\n\nwidget = a reload-safe panel\n", encoding="utf-8")
    return ticket_path


def test_context_pack_carries_what_the_ticket_omits(tmp_path: Path) -> None:
    ticket_path = make_repo(tmp_path)
    ticket = parse_ticket(ticket_path)

    pack = build_context_pack(tmp_path, ticket)

    assert "# Context pack: 07: Add the widget" in pack
    assert "## Goal" in pack
    assert "A widget that survives reloads." in pack
    assert "Read CONTEXT.md first." in pack          # project entry doc, not in the ticket
    assert "widget = a reload-safe panel" in pack    # glossary line
    assert "- 06: " in pack                          # blocking neighbour listed
    assert "python -m pytest tests/test_widget.py -q" in pack


def test_context_pack_reports_earlier_runs(tmp_path: Path) -> None:
    ticket_path = make_repo(tmp_path)
    ticket = parse_ticket(ticket_path)
    run_dir = tmp_path / ".dispatch" / "runs" / "07-20260101T000000000000Z-aaaaaa"
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(
        json.dumps({"run_id": run_dir.name, "ticket_id": "07", "state": "failed", "created_at": "2026-01-01T00:00:00+00:00"}),
        encoding="utf-8",
    )
    (run_dir / "verify.json").write_text(json.dumps({"status": "failed"}), encoding="utf-8")

    pack = build_context_pack(tmp_path, ticket)

    assert "07-20260101T000000000000Z-aaaaaa" in pack
    assert "verify=failed" in pack


def test_write_context_pack_creates_file(tmp_path: Path) -> None:
    ticket_path = make_repo(tmp_path)
    ticket = parse_ticket(ticket_path)

    target = write_context_pack(tmp_path, ticket)

    assert target == context_path(tmp_path, "07")
    assert target.is_file()
    assert target.read_text(encoding="utf-8").startswith("# Context pack")
