# 02: Dependency graph and wave planning

**What to build:** A dispatcher can run plan and see topological waves of tickets, the current frontier, and same-wave write-scope conflicts, with deterministic JSON output for scripts.

**Blocked by:** 01
**Status:** done

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: src/agent_dispatch/graph.py
- Write scope: src/agent_dispatch/cli.py
- Write scope: tests/test_graph.py
- Write scope: tests/test_cli_plan.py
- Read scope: .scratch/agent-dispatch-v0/spec.md
- Verify: python -m pytest tests/test_graph.py tests/test_cli_plan.py -q

## Acceptance

- [x] Independent tickets land in the same earliest wave; a dependent ticket lands after every blocker.
- [x] A cycle is excluded from waves and reported as an error.
- [x] Two tickets in the same wave with overlapping write scopes produce a conflict entry.
- [x] Disjoint write scopes in the same wave produce no conflict.
- [x] dispatch plan --json returns waves, frontier, blocked map, and conflicts.
