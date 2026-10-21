# 01: Ticket schema, parser, and lint

**What to build:** A planner can create one Markdown ticket with the dispatch metadata and run lint to get stable, non-zero failures for missing fields, duplicate ids, invalid scope paths, self-dependencies, unknown dependencies, and cycles.

**Blocked by:** None
**Status:** done

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: src/agent_dispatch/ticket.py
- Write scope: src/agent_dispatch/cli.py
- Write scope: tests/test_ticket.py
- Write scope: tests/test_cli_ticket.py
- Read scope: .scratch/agent-dispatch-v0/spec.md
- Verify: python -m pytest tests/test_ticket.py tests/test_cli_ticket.py -q

## Acceptance

- [x] A valid ticket parses its id, title, what-to-build, owner, risk, dependencies, write/read scopes, verify commands, and acceptance items.
- [x] Repeated Write scope and Verify lines accumulate in order.
- [x] Missing owner, risk, write scope, verify command, acceptance item, or what-to-build produces a documented error code.
- [x] Duplicate ids, self-dependencies, unknown dependencies, absolute scopes, and parent-directory scopes are rejected.
- [x] A cycle is reported by lint with the participating ids.
- [x] dispatch lint exits 0 on valid tickets and non-zero on invalid tickets.
