# 27: 不可信摘录带来源标注与自适应围栏

## What to build

执行端拿到的上下文包与失败反馈里，凡是执行端可控内容（同票前序运行的执行器错误、上一次的失败原因）都带来源标注和「数据非指令」声明，且围栏长度随内容自适应——执行器输出里嵌反引号串加祈使句时，无法提前闭合围栏冒充顶层指令。项目入口文档仍是可信指令源、保留指令地位，但摘录块标注它只代表本仓视角。

两条通道必须同等对待：只改上下文包等于关后门开前门，失败原因还会经反馈文件进下一次尝试。两处共用同一个围栏辅助函数，避免实现漂移。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L2
- Persona: dispatcher.md
- Requires: local
- Write scope: src/agent_dispatch/context.py
- Write scope: src/agent_dispatch/feedback.py
- Write scope: src/agent_dispatch/fence.py
- Write scope: tests/test_context.py
- Write scope: tests/test_feedback.py
- Write scope: tests/test_cli_auto_protocol.py
- Read scope: docs/specs/dispatch-trust-boundaries.md
- Read scope: docs/selection/dispatch-trust-boundaries/**
- Verify: python -m pytest -q tests/test_context.py tests/test_feedback.py tests/test_cli_auto_protocol.py

## Acceptance

- [ ] 上下文包里的执行端可控摘录带来源标注与「数据非指令」声明；项目入口文档保留指令地位但标注仅代表本仓视角
- [ ] 围栏长度取内容中最长反引号串长度加一与三的最小上限，含三反引号的注入内容被完整包在围栏内，含四反引号时自动升五（用真实攻击样本断言，不只测声明字符串存在）
- [ ] 失败反馈里的失败原因与上下文摘录同等对待：同样的声明与自适应围栏，两处共用一个辅助函数
