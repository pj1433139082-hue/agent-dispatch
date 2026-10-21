from __future__ import annotations

from pathlib import Path

from agent_dispatch.brief import (
    SECTIONS,
    approval_status,
    approve_brief,
    check_brief,
    check_brief_text,
    ensure_brief,
    render_template,
)
from agent_dispatch.ticket import parse_ticket

TICKET = """# 08: Ship the panel

**What to build:** A panel.
**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: src/panel.py
- Verify: python -m pytest tests/test_panel.py -q

## Acceptance

- [ ] The panel ships.
"""


def make_ticket(tmp_path: Path):
    (tmp_path / "tickets").mkdir()
    path = tmp_path / "tickets" / "08-panel.md"
    path.write_text(TICKET, encoding="utf-8")
    return parse_ticket(path)


def filled(text: str) -> str:
    for section in SECTIONS:
        text = text.replace(f"## {section}\n\n<", f"## {section}\n\nreal content <")
    return text


def test_template_lists_every_section(tmp_path: Path) -> None:
    ticket = make_ticket(tmp_path)
    template = render_template(ticket)
    for section in SECTIONS:
        assert f"## {section}" in template


def test_placeholder_brief_fails(tmp_path: Path) -> None:
    ticket = make_ticket(tmp_path)
    ok, problems = check_brief_text(render_template(ticket))
    assert ok is False
    assert len(problems) == len(SECTIONS)


def test_filled_brief_passes_and_can_be_approved(tmp_path: Path) -> None:
    ticket = make_ticket(tmp_path)
    target = ensure_brief(tmp_path, ticket)
    target.write_text(filled(target.read_text(encoding="utf-8")), encoding="utf-8")

    ok, problems = check_brief(tmp_path, ticket.id)
    assert ok is True, problems

    record = approve_brief(tmp_path, ticket, "lead")
    assert record.is_file()
    accepted, why = approval_status(tmp_path, ticket)
    assert accepted is True, why


def test_editing_the_brief_after_approval_invalidates_it(tmp_path: Path) -> None:
    ticket = make_ticket(tmp_path)
    target = ensure_brief(tmp_path, ticket)
    target.write_text(filled(target.read_text(encoding="utf-8")), encoding="utf-8")
    approve_brief(tmp_path, ticket, "lead")

    target.write_text(target.read_text(encoding="utf-8") + "\nextra change\n", encoding="utf-8")

    accepted, why = approval_status(tmp_path, ticket)
    assert accepted is False
    assert "被改动" in why
