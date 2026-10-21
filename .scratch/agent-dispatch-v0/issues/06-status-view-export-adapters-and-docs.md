# 06: Status view, export adapters, and docs

**What to build:** A maintainer can read status as text or JSON and export ready work to DSH team, DSH board, Codex, and generic markdown, with a README quickstart that reproduces the flow in a clean directory.

**Blocked by:** 02, 05
**Status:** done

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: src/agent_dispatch/export.py
- Write scope: src/agent_dispatch/cli.py
- Write scope: tests/test_export.py
- Write scope: tests/test_cli_export.py
- Write scope: README.md
- Read scope: .scratch/agent-dispatch-v0/spec.md
- Verify: python -m pytest tests/test_export.py tests/test_cli_export.py -q

## Acceptance

- [x] status shows every ticket with its effective state and next frontier, and status --json is valid JSON.
- [x] dsh-team export emits subject, description, ownerName, blockedBy, and writeScopes for ready tasks.
- [x] dsh-board export emits board cards with id, title, status, description, tags, and permission.
- [x] codex export emits one work-order-style markdown section per ready ticket.
- [x] generic export emits deterministic markdown sorted by ticket id.
- [x] README quickstart covers new, lint, plan, render, verify, review, status, and export.
