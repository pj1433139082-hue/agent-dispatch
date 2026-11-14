from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from agent_dispatch.export import PERMISSIONS
from agent_dispatch.ticket import Ticket
from agent_dispatch.workorder import RECEIPT_SCHEMA, render_work_order


def ticket() -> Ticket:
    return Ticket(
        id="01",
        title="Build the parser",
        path=Path("01-parser.md"),
        what_to_build="A planner can parse one ticket and lint it.",
        owner="implementer",
        risk="L1",
        depends_on=(),
        write_scope=("src/agent_dispatch/ticket.py", "tests/test_ticket.py"),
        read_scope=("docs/**",),
        verify=("python -m pytest tests/test_ticket.py -q",),
        acceptance=("The parser returns the ticket id.", "The linter accepts a complete ticket."),
    )


def test_work_order_is_self_contained() -> None:
    text = render_work_order(
        ticket(),
        {"run_id": "run-1", "ticket_hash": "abc123", "base_commit": "deadbeef"},
    )

    assert "# Work order: 01: Build the parser" in text
    assert "A planner can parse one ticket and lint it." in text
    assert "- Owner: implementer" in text
    assert "- Risk: L1" in text
    assert "- src/agent_dispatch/ticket.py" in text
    assert "- tests/test_ticket.py" in text
    assert "- docs/**" in text
    assert "- [ ] The parser returns the ticket id." in text
    assert "- [ ] The linter accepts a complete ticket." in text
    assert "python -m pytest tests/test_ticket.py -q" in text
    assert "run-1" in text
    assert "abc123" in text
    assert "deadbeef" in text


def test_receipt_schema_is_documented_in_the_work_order() -> None:
    text = render_work_order(ticket(), {"run_id": "run-1", "ticket_hash": "abc", "base_commit": ""})

    assert "Receipt contract" in text
    assert "receipt.json" in text
    for field in RECEIPT_SCHEMA["required"]:
        assert f"\"{field}\"" in text or field in text
    assert "it does not count as recomputable evidence" in text
    assert "Without file/inline/absent evidence, the criterion is degraded" in text


def test_work_order_tells_the_executor_not_to_edit_status() -> None:
    text = render_work_order(ticket(), {"run_id": "run-1", "ticket_hash": "abc", "base_commit": ""})

    assert "do not edit the ticket" in text.lower()


def test_permission_section_uses_shared_risk_mapping() -> None:
    for risk, permission in PERMISSIONS.items():
        text = render_work_order(replace(ticket(), risk=risk), {})
        assert f"Allowed mode for this ticket's risk: `{permission}`" in text
    for risk in ("", "unknown"):
        text = render_work_order(replace(ticket(), risk=risk), {})
        assert f"Allowed mode for this ticket's risk: `{PERMISSIONS['L1']}`" in text


def test_permission_section_explains_enforcement_and_team_boundary() -> None:
    text = render_work_order(ticket(), {})

    assert "filesystem effects only" in text
    assert "network or\n  process visibility isolation" in text
    assert "On Windows enforcement may be partial" in text
    assert "One-shot delegation and named teammates: **not enforced**" in text
    assert "permission parameter is **passed**" in text
    assert "enforcement in the\n  execution session has not been established" in text
    assert "parent card uses the highest risk level in the wave" in text
    assert "ticket's allowed mode above is not a per-teammate sandbox" in text
