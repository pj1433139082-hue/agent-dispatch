# ADR-0010 auto 的协议挂载方式

- 状态：Accepted（2026-10-22，grill-with-docs 第二轮，甲方「都按照推荐」）
- 触发：检查 `dispatch auto` 现状：386 行实现里 `context` / `brief` / `checkpoint` / `closeout` / `env_hint` 出现次数**全为 0**，只有失败回灌；且 `--until land` 直接 `land_run()`，绕过 `--require-closeout`。实测一次 auto：产出仅 `auto.json / logs / receipt.json / run.json / verify.json / work-order.md`，work-order 里没有 context 段、没有环境前置段。

## 1. 决策

### D1 auto 保持"单步推进器"，不做多票编排

auto 的职责是「跑一次执行 + 串门禁」：render → 执行器 → verify →（可选）review → land。多票按依赖编排属于 **Pipeline**（尚不存在），不塞进 auto，避免它与 render/brief/checkpoint/closeout/land 职责重叠、变成第二个编排器。

### D2 协议靠开关挂载：`--protocol full`，默认关

默认行为不变（老调用、现有测试全不动）。加 `--protocol full` 后按固定顺序执行：

1. render 阶段注入 **context pack**（`with_context`）+ **env hint**（`--env-hint`）；
2. 若带 `--require-brief`：检查 brief 审批，未通过则**不开跑**（auto 自己建 run，必须在这里拦，不能只靠 render 的 flag）；
3. 执行器（第 n>1 次带 `DISPATCH_FEEDBACK` 回灌）；
4. verify；
5. **发布 checkpoint**（每次 verify 之后一代，标签 `attempt-<n>`）；
6. **closeout**（写 `closeout.json/md`）；
7. `--until land` 时：**closeout 必须 pass** 才 land，否则 `status=closeout-failed` 并停。

### D3 评审输入强制用 review packet

`--until land` 时先生成 **review packet**（票据快照 + diff + 回执 + 验收证据，全部带哈希），把 `DISPATCH_REVIEW_PACKET` 作为环境变量交给 reviewer；reviewer 不再直接读活动 worktree。理由：评审要对着**冻结的输入**下结论，而不是对着执行者刚离开的现场。

### D4 术语分家

- **Auto run**：单票自动推进，可带协议门禁，但**不做多票编排**。
- **Pipeline**：多票按 `blocked-by` 编排执行（当前不存在，先占词不实现）。

### D5 `--until` 是"停靠点"，不是"协议深度"

- `--until review`：停在 review（不跑 closeout）；
- `--until land`：必须过独立评审 + closeout 才 land。
- 协议开关（`--protocol`）只管"中间要不要注入 context / 检查 brief / 发 checkpoint"，与停靠点正交。

## 2. 后果

- 正面：老调用零影响；要协议的人一个 flag 全拿到；`--until land` 不再能绕过 closeout。
- 负面：flag 组合变多（`--protocol` × `--until` × `--require-brief`），需要一张组合真值表进 SKILL；实现上 auto 要复用 context/brief/checkpoint/closeout 四个模块（不能复制逻辑）。
- 待办：`--protocol full` 的端到端测试要覆盖"brief 未过 → 不开跑"与"closeout fail → 不 land"两条负路径。
