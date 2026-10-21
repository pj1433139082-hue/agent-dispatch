# 05: Review gate and state transitions

**What to build:** A reviewer can pass or fail a verified run, with self-review rejected and an auditable review record; pass moves the ticket to done and fail moves it to failed.

**Blocked by:** 04
**Status:** done

## Dispatch

- Owner: reviewer
- Risk: L1
- Write scope: src/agent_dispatch/review.py
- Write scope: src/agent_dispatch/cli.py
- Write scope: tests/test_review.py
- Write scope: tests/test_cli_review.py
- Read scope: .scratch/agent-dispatch-v0/spec.md
- Verify: python -m pytest tests/test_review.py tests/test_cli_review.py -q

## Acceptance

- [x] Review is refused when verify has not passed.
- [x] Review is refused when the reviewer equals the ticket owner or the claiming agent.
- [x] A pass writes review.json and moves state to done.
- [x] A fail writes review.json and moves state to failed.
- [x] Review requires a non-empty verdict and reviewer identity.
