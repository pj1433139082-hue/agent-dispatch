# 03: Work order rendering and run claiming

**What to build:** A dispatcher can render a ticket into a self-contained work order with goal, scopes, acceptance, verification commands, and receipt contract; the run is recorded and the ticket moves out of ready.

**Blocked by:** 01
**Status:** done

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: src/agent_dispatch/state.py
- Write scope: src/agent_dispatch/workorder.py
- Write scope: src/agent_dispatch/cli.py
- Write scope: tests/test_workorder.py
- Write scope: tests/test_cli_render.py
- Read scope: .scratch/agent-dispatch-v0/spec.md
- Verify: python -m pytest tests/test_workorder.py tests/test_cli_render.py -q

## Acceptance

- [x] Rendering a ready ticket writes a run directory with run.json and work-order.md.
- [x] The work order contains the ticket goal, owner, risk, write scope, read scope, acceptance items, verification commands, and receipt schema.
- [x] Rendering records the ticket content hash and current git commit.
- [x] Rendering a ticket with unfinished dependencies is refused.
- [x] Rendering moves state to claimed and a start command moves it to running.
- [x] A second render while a run is active is refused unless the previous run failed.
