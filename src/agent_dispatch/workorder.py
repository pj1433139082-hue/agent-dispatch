"""Work order rendering: the executor's self-contained brief."""

from __future__ import annotations

import json

from .ticket import Ticket

RECEIPT_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["ticket_id", "run_id", "status", "summary", "evidence"],
    "properties": {
        "ticket_id": {"type": "string"},
        "run_id": {"type": "string"},
        "status": {"enum": ["done", "failed"]},
        "summary": {"type": "string"},
        "evidence": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}


def _bullets(items: tuple[str, ...]) -> str:
    if not items:
        return "- (none)"
    return "\n".join(f"- {item}" for item in items)


def render_work_order(ticket: Ticket, run: dict[str, object]) -> str:
    acceptance = "\n".join(f"- [ ] {item}" for item in ticket.acceptance) or "- (none)"
    commands = "\n".join(ticket.verify) or "echo 'no verification command declared'"
    receipt = json.dumps(RECEIPT_SCHEMA, indent=2, ensure_ascii=False)
    return f"""# Work order: {ticket.id}: {ticket.title}

Run ID: {run.get("run_id", "")}
Ticket hash: {run.get("ticket_hash", "")}
Base commit: {run.get("base_commit", "") or "(not a git repository)"}

## Goal

{ticket.what_to_build}

## Owner and risk

- Owner: {ticket.owner}
- Risk: {ticket.risk}

## Write scope

{_bullets(ticket.write_scope)}

## Read scope

{_bullets(ticket.read_scope)}

## Acceptance

{acceptance}

## Verification

Run these commands from the repository root:

\u0060\u0060\u0060bash
{commands}
\u0060\u0060\u0060

## Receipt contract

Write \u0060receipt.json\u0060 in this run directory. It must validate against:

\u0060\u0060\u0060json
{receipt}
\u0060\u0060\u0060

Do not edit the ticket, do not change its status, and do not claim done yourself.
The verifier reruns the commands and checks the real git diff against the write scope.
"""
