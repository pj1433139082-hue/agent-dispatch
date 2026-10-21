"""Read-only status views and export adapters."""

from __future__ import annotations

import json

from .graph import build_plan
from .persona import persona_section
from .ticket import Ticket

PERMISSIONS = {
    "L0": "read-only",
    "L1": "workspace-write",
    "L2": "workspace-write",
    "L3": "danger-full-access",
    "L4": "danger-full-access",
}


def _done(states: dict[str, str]) -> set[str]:
    return {ticket_id for ticket_id, state in states.items() if state == "done"}


def _dispatchable(state: str | None) -> bool:
    return state in (None, "ready", "failed")


def _blocked_by(ticket: Ticket, done: set[str]) -> list[str]:
    return sorted(dep for dep in ticket.depends_on if dep not in done)


def status_document(
    tickets: list[Ticket],
    states: dict[str, str] | None = None,
    done: set[str] | None = None,
) -> dict[str, object]:
    states = dict(states or {})
    done = done if done is not None else _done(states)
    plan = build_plan(tickets, done=done)
    ready_frontier = [
        ticket_id
        for ticket_id in plan.frontier
        if _dispatchable(states.get(ticket_id))
    ]
    rows: list[dict[str, object]] = []
    for ticket in sorted(tickets, key=lambda item: item.id):
        stored = states.get(ticket.id)
        if stored is None:
            state = "blocked" if _blocked_by(ticket, done) else "ready"
        else:
            state = stored
        rows.append(
            {
                "id": ticket.id,
                "title": ticket.title,
                "state": state,
                "blocked_by": _blocked_by(ticket, done),
                "next": ticket.id in ready_frontier,
                "owner": ticket.owner,
                "risk": ticket.risk,
            }
        )
    return {
        "tickets": rows,
        "frontier": ready_frontier,
        "conflicts": [conflict.to_dict() for conflict in plan.conflicts],
    }


def ready_tickets(
    tickets: list[Ticket], states: dict[str, str] | None = None
) -> list[Ticket]:
    states = dict(states or {})
    done = _done(states)
    plan = build_plan(tickets, done=done)
    ready = [
        ticket_id
        for ticket_id in plan.frontier
        if _dispatchable(states.get(ticket_id))
    ]
    by_id = {ticket.id: ticket for ticket in tickets}
    return [by_id[ticket_id] for ticket_id in sorted(ready)]


def _description(ticket: Ticket) -> str:
    persona = persona_section(ticket)
    return ticket.what_to_build + (f"\n\n{persona}" if persona else "")


def _agent_team(tickets: list[Ticket]) -> str:
    if not tickets:
        return "# Agent Team dispatch\n\nNo ready tickets.\n"
    sections = "\n".join(ticket_section(ticket) for ticket in tickets).rstrip()
    return f"""# Agent Team dispatch

You are the Team Lead for this dispatch wave. Use one teammate per ticket.

Before a teammate writes code, require a short brief: goal, files to touch, plan, risks, and open questions. Review that brief and approve, correct, or stop the teammate before implementation starts.

Each teammate must stay inside the ticket's write scope, run the ticket's Verify command, and leave a receipt with evidence. Do not mark a ticket complete without verification evidence.

## Tickets

{sections}
"""


def _dsh_team(tickets: list[Ticket]) -> str:
    payload = [
        {
            "subject": ticket.title,
            "description": _description(ticket),
            "ownerName": ticket.owner,
            "blockedBy": [],
            "writeScopes": list(ticket.write_scope),
        }
        for ticket in tickets
    ]
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _dsh_board(tickets: list[Ticket], project: str) -> str:
    from .dsh import build_card_actions, normalize_base_url

    actions = build_card_actions(tickets, project=project)
    document = {
        "format": "dsh-board",
        "version": 2,
        "endpoint": normalize_base_url() + "/action",
        "actions": actions,
    }
    return json.dumps(document, indent=2, ensure_ascii=False)


def ticket_section(ticket: Ticket) -> str:
    acceptance = "\n".join(f"- [ ] {item}" for item in ticket.acceptance) or "- (none)"
    commands = "\n".join(ticket.verify) or "echo 'no verification command declared'"
    write_scope = "".join(f"- {item}\n" for item in ticket.write_scope) or "- (none)\n"
    persona = persona_section(ticket)
    persona_block = f"\n{persona}\n" if persona else ""
    return f"""## {ticket.id}: {ticket.title}

Owner: {ticket.owner}
Risk: {ticket.risk}
{persona_block}
### Goal

{ticket.what_to_build}

### Write scope

{write_scope}
### Acceptance

{acceptance}

### Verify

```bash
{commands}
```
"""


def export_text(
    tickets: list[Ticket],
    fmt: str,
    states: dict[str, str] | None = None,
    project: str = "default",
) -> str:
    ready = ready_tickets(tickets, states)
    if fmt == "agent-team":
        return _agent_team(ready)
    if fmt == "dsh-team":
        return _dsh_team(ready) + "\n"
    if fmt == "dsh-board":
        return _dsh_board(ready, project) + "\n"
    if fmt == "codex":
        return "\n".join(ticket_section(ticket) for ticket in ready).rstrip() + "\n"
    if fmt == "generic":
        if not ready:
            return "# Dispatch ready work\n\nNo ready tickets.\n"
        body = "\n".join(ticket_section(ticket) for ticket in ready).rstrip()
        return f"# Dispatch ready work\n\n{body}\n"
    raise ValueError(f"unknown export format: {fmt}")
