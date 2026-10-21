# 04: Independent verification gate

**What to build:** A verifier can run verify against a run receipt; dispatch re-runs the declared commands, checks the real git diff against write scope, hashes evidence, and only then moves the ticket to review.

**Blocked by:** 03
**Status:** done

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: src/agent_dispatch/verify.py
- Write scope: src/agent_dispatch/cli.py
- Write scope: tests/test_verify.py
- Write scope: tests/test_cli_verify.py
- Read scope: .scratch/agent-dispatch-v0/spec.md
- Verify: python -m pytest tests/test_verify.py tests/test_cli_verify.py -q

## Acceptance

- [x] A passing receipt plus passing commands plus in-scope diff plus present evidence moves state to review.
- [x] A missing receipt, non-done receipt, failed command, out-of-scope file, missing evidence file, or ticket changed after render fails verification.
- [x] verify.json records each check, changed files, command exit codes, log hashes, and evidence hashes.
- [x] Verification never trusts the receipt's changed-files claim.
- [x] The failure path writes a failed state and exits non-zero.
