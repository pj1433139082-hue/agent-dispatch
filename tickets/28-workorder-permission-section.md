# 28: 工单写明权限模式与强制状态

## What to build

每份工单都带权限段，执行端动手前就能看到自己的边界：允许哪种权限模式、该模式只约束文件系统效果而不承诺网络与进程可见性、Windows 平台可能只是部分强制、以及这条边界在当前执行端是「已传参」还是「未强制」。团队模式额外说明父卡取全波最高风险等级，让同波低风险票的成员知道自己实际拿到的是什么权限。

权限映射复用既有那一份，不新建第二份定义。能力边界要诚实：一次性委派与具名成员两条路径拿不到权限参数，只能声明并标注未强制；看板路径已传参但不声称已强制生效。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Requires: local
- Write scope: src/agent_dispatch/workorder.py
- Write scope: tests/test_workorder.py
- Read scope: src/agent_dispatch/export.py
- Read scope: src/agent_dispatch/dsh.py
- Read scope: docs/specs/dispatch-trust-boundaries.md
- Read scope: docs/selection/dispatch-trust-boundaries/02-sources.md
- Verify: python -m pytest -q tests/test_workorder.py tests/test_dsh.py

## Acceptance

- [ ] 工单含权限段，写明允许模式、仅文件系统语义、Windows 可能部分强制、以及已传参或未强制的区分
- [ ] 团队模式的工单说明父卡取波内最高风险等级，不改该取值语义本身
- [ ] 权限映射只有一份定义（工单复用既有映射，不复制第二份），且既有工单与看板测试不回归
