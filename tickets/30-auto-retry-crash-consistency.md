# 30: auto 内循环重试的崩溃一致性

## What to build

自动派单在一次运行内多次执行执行端时，每一次重试都要在**开始之前**就记进手账，使进程被中断（超时被杀、崩溃、用户打断）后已发生的重试仍然算进该票额度。当前实现把记账放在自动流程返回之后，进程若在第二次或后续尝试中中断，那些重试不入账，后续可继续跑，额度因此不能可靠累计。

票 29 已把普通重派、失败后重新渲染、归档后重开三条路径的额度做实，并让自动流程按剩余额度收紧次数、逐次记账；本票补的是**崩溃窗口**这一段，属票 29 写域之外（要改自动流程本身），故单独开票。

来源：票 29 第三轮独立评审（codex-reviewer）提出，Lead 复核成立但判定属票外范围，见 .dispatch/runs/29-…/auto/review-fix-2.md 与本轮评审记录。

**Blocked by:** 29
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L2
- Persona: dispatcher.md
- Requires: local
- Write scope: src/agent_dispatch/auto.py
- Write scope: src/agent_dispatch/export.py
- Write scope: tests/test_cli_auto.py
- Write scope: tests/test_auto_retry_feedback.py
- Read scope: src/agent_dispatch/cli.py
- Read scope: docs/specs/dispatch-trust-boundaries.md
- Verify: python -m pytest -q tests/test_cli_auto.py tests/test_auto_retry_feedback.py tests/test_cli_retry.py

## Acceptance

- [ ] 自动流程在每次执行端尝试**之前**就把该次重试记进手账；模拟进程在第二次尝试中被中断后，该票额度仍已消耗对应次数（用真实命令行或可中断的子进程断言，不是纯函数）
- [ ] 记账移到尝试前后不重复计数：同一次尝试不得既由自动流程记账、又由命令行收口记账；正常完成的自动流程其额度消耗与尝试次数一致
- [ ] 既有自动流程行为不回归：反馈注入、checkpoint、评审门与额度收紧语义保持；旧运行缺新字段仍可读
