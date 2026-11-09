# 29: 重派额度按票累计并挡住超限票

## What to build

同一张票的重派额度按票累计、落在归档不会删的手账里：失败后重新渲染出新运行不重置额度，归档后重开也不重置（归档记录本身计入已用额度）。额度用尽的票不再出现在可派集合与导出结果里，自动派单不会继续投它。超限时只说已达上限需人工评估，不再给出绕过命令；逃生参数保留供工具故障等外部原因使用，但强制填理由并记进手账，便于事后区分人工决断与机器蛮干。

计数属于账不属于手，所以不存运行态索引（票条目会被状态写入整体覆盖、归档会删整条票），也不存票面（票面签过哈希且执行端禁止改票）。拦截点放在就绪票筛选这一唯一收口，使看板投递与文本导出两条路径同时生效。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L2
- Persona: dispatcher.md
- Requires: local
- Write scope: src/agent_dispatch/cli.py
- Write scope: src/agent_dispatch/export.py
- Write scope: tests/test_cli_retry.py
- Write scope: tests/test_export.py
- Write scope: tests/test_cli_export.py
- Read scope: src/agent_dispatch/lifecycle.py
- Read scope: src/agent_dispatch/state.py
- Read scope: docs/specs/dispatch-trust-boundaries.md
- Verify: python -m pytest -q tests/test_cli_retry.py tests/test_export.py tests/test_cli_export.py

## Acceptance

- [ ] 重派额度按票累计并落在追加式手账里；失败后重新渲染、归档后重开两条路径都不重置额度（用真实命令行序列断言，不是纯函数）
- [ ] 额度用尽的票不进入可派集合与导出结果；就绪票筛选的新参数可选且默认不改变既有行为
- [ ] 超限提示不含绕过命令；逃生参数仍可用、强制理由、并在手账里标记是否使用了逃生参数
