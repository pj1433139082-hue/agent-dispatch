"""Work order rendering: the executor's self-contained brief."""

from __future__ import annotations

import json

from .persona import persona_section
from .ticket import Ticket

EVIDENCE_ITEM_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["kind"],
    "properties": {
        "kind": {"enum": ["file", "inline", "absent", "command", "note"]},
        "path": {"type": "string"},
        "content": {"type": "string"},
        "sha256": {"type": "string"},
        "command": {"type": "string"},
        "exit_code": {"type": "integer"},
        "note": {"type": "string"},
    },
    "additionalProperties": False,
}

CRITERION_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["id", "verdict", "evidence"],
    "properties": {
        "id": {"type": "integer", "minimum": 1},
        "verdict": {"enum": ["pass", "fail"]},
        "note": {"type": "string"},
        "evidence": {
            "type": "array",
            "minItems": 1,
            "items": EVIDENCE_ITEM_SCHEMA,
        },
    },
    "additionalProperties": False,
}

RECEIPT_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["ticket_id", "run_id", "status", "summary", "criteria"],
    "properties": {
        "ticket_id": {"type": "string"},
        "run_id": {"type": "string"},
        "status": {"enum": ["done", "failed"]},
        "summary": {"type": "string"},
        "persona": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "sha256": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "criteria": {"type": "array", "minItems": 1, "items": CRITERION_SCHEMA},
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
    persona = persona_section(ticket, "##")
    persona_block = f"\n{persona}\n" if persona else ""
    execution_root = str(run.get("execution_root") or "(main checkout)")
    branch = str(run.get("worktree_branch") or "(none)")
    return f"""# Work order: {ticket.id}: {ticket.title}

Run ID: {run.get("run_id", "")}
Ticket hash: {run.get("ticket_hash", "")}
Base commit: {run.get("base_commit", "") or "(not a git repository)"}
Execution root: {execution_root}
Worktree branch: {branch}
Run directory: .dispatch/runs/{run.get("run_id", "")}

## Goal

{ticket.what_to_build}

## Owner and risk

- Owner: {ticket.owner}
- Risk: {ticket.risk}
{persona_block}
## Write scope

{_bullets(ticket.write_scope)}

## Read scope

{_bullets(ticket.read_scope)}

## Acceptance

{acceptance}

## Verification

Run these commands from the **execution root** through the platform shell
(`cmd.exe` on Windows, `/bin/sh` elsewhere; `&&`, pipes, and quoted paths are supported):

```bash
{commands}
```

## Receipt contract

Write `receipt.json` in the run directory. It must validate against:

```json
{receipt}
```

Provide exactly one criterion per acceptance item, numbered 1..{len(ticket.acceptance)}.
Every criterion needs at least one evidence item. Evidence kinds:

- `file`: a path relative to the run directory, or to the execution root (worktree) — the verifier tries the run directory first, then the worktree; it hashes whatever it finds.
- `inline`: literal content; include an optional sha256 to bind it.
- `absent`: a path that must not exist.
- `command`: a command and exit_code the executor observed (not rerun by verify).
- `note`: an attested human/agent statement; a criterion supported only by notes is degraded.

If the ticket has a persona, copy `persona` from `run.json` into the receipt
(top-level, not inside criteria): `{{"persona": {{"source": "...", "sha256": "..."}}}}`.
A missing or mismatching persona turns the verification into `degraded`.

The verifier reruns the verification commands from the execution root, checks the
real git diff against the write scope, and rejects a polluted main checkout.
Do not edit the ticket, do not change its status, and do not claim done yourself.
"""
