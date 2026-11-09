"""Read-only status views and export adapters."""

from __future__ import annotations

import json
from pathlib import Path

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
    include_declared_done: bool = False,
    exhausted: set[str] | None = None,
) -> dict[str, object]:
    states = dict(states or {})
    done = done if done is not None else _done(states)
    # 票面 **Status:** 是作者标记，不是事实（SKILL.md:276）。done 集合默认只来自
    # state.json；票面自述不得解锁下游依赖。迁移场景可显式打开 include_declared_done。
    if include_declared_done:
        done = set(done) | {
            ticket.id for ticket in tickets if str(getattr(ticket, "status", "")).strip().lower() == "done"
        }
    else:
        done = set(done)
    plan = build_plan(tickets, done=done)
    ready_frontier = [
        ticket_id
        for ticket_id in plan.frontier
        if _dispatchable(states.get(ticket_id)) and ticket_id not in (exhausted or set())
    ]
    rows: list[dict[str, object]] = []
    for ticket in sorted(tickets, key=lambda item: item.id):
        stored = states.get(ticket.id)
        if stored is None:
            declared = str(getattr(ticket, "status", "")).strip().lower()
            if declared in {"done", "failed", "blocked", "review"}:
                state = declared
            else:
                state = "blocked" if _blocked_by(ticket, done) else "ready"
        else:
            state = stored
        rows.append(
            {
                "id": ticket.id,
                "title": ticket.title,
                "state": state,
                "hint": ("retry limit reached; human evaluation required" if ticket.id in (exhausted or set())
                         else "dispatch retry " + ticket.id if state == "failed" else ""),
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


RETRY_LIMIT = 3


def retry_usage(root: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name in ("retries.jsonl", "dropped.jsonl"):
        path = Path(root) / ".dispatch" / "ledger" / name
        if not path.is_file():
            continue
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                    ticket_id = row.get("ticket_id") if isinstance(row, dict) else None
                    if isinstance(ticket_id, str) and ticket_id:
                        counts[ticket_id] = counts.get(ticket_id, 0) + 1
                except (ValueError, TypeError):
                    continue
    return counts


def exhausted_tickets(root: Path) -> set[str]:
    return {ticket_id for ticket_id, count in retry_usage(root).items() if count >= RETRY_LIMIT}


def ready_tickets(
    tickets: list[Ticket], states: dict[str, str] | None = None,
    exhausted: set[str] | None = None,
) -> list[Ticket]:
    states = dict(states or {})
    done = _done(states)
    plan = build_plan(tickets, done=done)
    ready = [
        ticket_id
        for ticket_id in plan.frontier
        if _dispatchable(states.get(ticket_id)) and ticket_id not in (exhausted or set())
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
    exhausted: set[str] | None = None,
) -> str:
    ready = ready_tickets(tickets, states, exhausted)
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
