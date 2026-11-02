from __future__ import annotations

import json
from pathlib import Path

from agent_dispatch.export import export_text, status_document
from agent_dispatch.ticket import Ticket


def ticket(
    ticket_id: str,
    *,
    depends_on: tuple[str, ...] = (),
    write_scope: tuple[str, ...] = ("src/agent_dispatch/export.py",),
    status: str = "",
) -> Ticket:
    return Ticket(
        id=ticket_id,
        title=f"Ticket {ticket_id}",
        path=Path(f"{ticket_id}.md"),
        what_to_build=f"Ship {ticket_id}.",
        owner="implementer",
        risk="L1",
        depends_on=depends_on,
        write_scope=write_scope,
        verify=("python -m pytest -q",),
        acceptance=(f"{ticket_id} works.",),
        status=status,
    )


def test_status_marks_blocked_and_frontier() -> None:
    document = status_document([ticket("A"), ticket("B", depends_on=("A",))], {})

    rows = {row["id"]: row for row in document["tickets"]}
    assert rows["A"]["state"] == "ready"
    assert rows["A"]["next"] is True
    assert rows["B"]["state"] == "blocked"
    assert rows["B"]["blocked_by"] == ["A"]
    assert document["frontier"] == ["A"]


def test_status_uses_stored_states() -> None:
    document = status_document([ticket("A"), ticket("B")], {"A": "done", "B": "running"})

    rows = {row["id"]: row for row in document["tickets"]}
    assert rows["A"]["state"] == "done"
    assert rows["B"]["state"] == "running"
    assert document["frontier"] == []


def test_dsh_team_export_has_the_team_task_fields() -> None:
    payload = json.loads(export_text([ticket("A")], "dsh-team"))

    assert payload == [
        {
            "subject": "Ticket A",
            "description": "Ship A.",
            "ownerName": "implementer",
            "blockedBy": [],
            "writeScopes": ["src/agent_dispatch/export.py"],
        }
    ]


def test_dsh_board_export_is_an_http_action_envelope() -> None:
    document = json.loads(export_text([ticket("A")], "dsh-board", project="probe"))

    assert document["format"] == "dsh-board"
    assert document["version"] == 2
    assert document["endpoint"].endswith("/api/task-board/action")
    action = document["actions"][0]
    assert action["action"]["kind"] == "create"
    card = action["action"]["input"]
    assert card["title"] == "A: Ticket A"
    assert card["description"] == "Ship A."
    assert card["tags"] == [{"name": "dispatch"}, {"name": "dispatch:A"}, {"name": "L1"}]
    assert card["permission"] == "workspace-write"


def test_agent_team_export_is_a_lead_brief_with_ticket_sections() -> None:
    text = export_text([ticket("A")], "agent-team")

    assert text.startswith("# Agent Team dispatch")
    assert "You are the Team Lead" in text
    assert "require a short brief" in text
    assert "## A: Ticket A" in text
    assert "Write scope" in text
    assert "Verify" in text


def test_codex_export_has_one_section_per_ready_ticket() -> None:
    text = export_text([ticket("B"), ticket("A")], "codex")

    assert text.count("## A: Ticket A") == 1
    assert text.count("## B: Ticket B") == 1
    assert "Write scope" in text
    assert "Verify" in text


def test_generic_export_is_sorted_by_ticket_id() -> None:
    text = export_text([ticket("B"), ticket("A")], "generic")

    assert text.index("## A:") < text.index("## B:")


def test_export_only_includes_ready_tickets() -> None:
    tickets = [ticket("A"), ticket("B", depends_on=("A",))]

    payload = json.loads(export_text(tickets, "dsh-team"))

    assert [item["subject"] for item in payload] == ["Ticket A"]


def test_status_marks_failed_ticket_as_retryable() -> None:
    document = status_document([ticket("A")], {"A": "failed"})

    rows = {row["id"]: row for row in document["tickets"]}
    assert rows["A"]["state"] == "failed"
    assert rows["A"]["next"] is True
    assert document["frontier"] == ["A"]


def test_export_includes_failed_tickets_for_a_retry() -> None:
    payload = json.loads(export_text([ticket("A")], "dsh-team", {"A": "failed"}))

    assert [item["subject"] for item in payload] == ["Ticket A"]


def test_declared_done_does_not_unlock_dependents() -> None:
    """A ticket file claiming done must not satisfy depends_on (SKILL.md:276)."""
    document = status_document(
        [ticket("A", status="done"), ticket("B", depends_on=("A",))],
        {},
    )

    rows = {row["id"]: row for row in document["tickets"]}
    assert rows["A"]["state"] == "done", "display still reflects what the author wrote"
    assert rows["B"]["state"] == "blocked", "declared-done must not unlock B"
    assert document["frontier"] == ["A"]


def test_declared_done_unlocks_dependents_when_explicitly_allowed() -> None:
    """The migration escape hatch restores the old behaviour."""
    document = status_document(
        [ticket("A", status="done"), ticket("B", depends_on=("A",))],
        {},
        include_declared_done=True,
    )

    rows = {row["id"]: row for row in document["tickets"]}
    assert rows["B"]["state"] == "ready"
    assert document["frontier"] == ["B"]


def test_stored_done_still_unlocks_dependents() -> None:
    """state.json remains the fact source and still satisfies depends_on."""
    document = status_document([ticket("A"), ticket("B", depends_on=("A",))], {"A": "done"})

    rows = {row["id"]: row for row in document["tickets"]}
    assert rows["B"]["state"] == "ready"
    assert document["frontier"] == ["B"]
