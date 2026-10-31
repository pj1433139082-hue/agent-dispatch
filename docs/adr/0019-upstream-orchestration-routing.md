# 上游编排层：路由，不重写

我们缺的不是 wayfinder / triage / phase boundaries 的实现，而是"什么时候该用它们"的规则。这一版把四条上游能力接进 dispatch-flow / tickets-skill / implement-skill：雾大先走 wayfinder（决策票不塞进 tickets/）、阶段交界按五选一做 continue/clear/handoff/subagent/compact、外部 issue/PR 先 triage、出界方向记 `.out-of-scope/`；brief 对 L3+/接口/跨模块票要求两个候选方案。**不新增 decision 命令**：决策票的载体是 wayfinder 的地图，不是 dispatch 的票。

**Considered Options**：给 dispatch 加 `Type: decision` 与 decision 命令（会把 lint/plan/verify 全搅一遍，且重复 wayfinder）；把 upstream 技能整份重写（丢上游更新）。

**Consequences**：dispatch 的票仍然只表示"执行"；决策票靠 wayfinder 管理；`.out-of-scope/` 随仓库提交，成为团队记忆。
