# 23: command 证据改为替换语义，挡住自述与掺沙

## What to build

`command` 证据（`verify.py:331-350`）只校验形状与 `exit_code == expect_exit`，返回 `attested: False`；`degraded` 仅在整条 criterion 全 attested 时置位（`:409`），故纯 command 回执得 `passed`，review 无需 `--accept-degraded`。

这与 `references/ticket-contract.md:79`「`passed`：所有 criterion 都有**可复算证据**」直接冲突。

**否决计数版**：`verify.py:391-392` 已要求证据数组非空，故"每 criterion ≥1 条可复算证据"边际作用为零；加一条无关的 `evidence/anything.txt` 即可绕过（`_evaluate_evidence` 从不校验证据与 criterion 的相关性）。

**采用替换语义**：command 不计入可复算证据。

**Blocked by:** 22
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L2
- Persona: dispatcher.md
- Write scope: src/agent_dispatch/verify.py
- Write scope: tests/test_verify_expect_exit.py
- Write scope: tests/test_cli_worktree.py
- Write scope: SKILL.md
- Write scope: references/ticket-contract.md
- Read scope: docs/specs/security-audit-fixes.md
- Verify: python -m pytest -q tests/test_verify_expect_exit.py tests/test_verify_mixed_note_evidence.py tests/test_cli_worktree.py

## Acceptance

- [ ] 纯 `command` 证据的 criterion 不再单独构成可复算证据（落入 degraded 通道）
- [ ] `[command, file]` 组合中 command 不计价，若此外无物证仍判非可复算（挡住掺沙）
- [ ] 既有混合证据契约不回归：file/inline/absent/command/note 混用仍得 `passed`
- [ ] `test_verify_expect_exit.py:17` 的 `assert attested is False` 已按显式口径变更同步修改
- [ ] `SKILL.md:666` 的 attested 口径与 `ticket-contract:79` 的 passed 定义一致（解决 C4 矛盾）
