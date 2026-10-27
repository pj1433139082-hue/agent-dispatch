# ADR-0008 派单生命周期与状态可恢复性

- 状态：Accepted（2026-10-22，grill-with-docs 第一轮，甲方「按照推荐」）
- 触发：2026-10-22 泵工程实战。三次翻车都不是"agent 不干活"，而是**派单生命周期没有观测手段**：lead 按"产物是否出现"判活，误杀 6 个子 agent；`state.json` 被一次 `reset --hard` 抹掉，三张票的 run 映射只能手补；执行者为了跑构建临时借用别的项目 `node_modules`。
- 影响范围：`agent-dispatch` 技能（seat / deadline / sweep / repair / env 契约 / 评审分档）；不改 DSH 平台。

## 1. 问题（均有实测）

| # | 现象 | 证据 |
|---|---|---|
| 1 | 名额是隐形的：`spawn_teammate` 报 `Team member limit 8 reached`，inactive 成员仍占位 | 2026-10-22 09:0x，pw03 派不出去 |
| 2 | 判活靠猜：子 agent 探索期不落盘，lead 以为死了就 `interrupt_agent`，会话记 `aborted/parent` | 6 个会话（oss-scout 22 次工具调用、search-scout 11、adversary 25、pw01/02/03 各 5–11）全被误杀 |
| 3 | 索引是单点：`state.json` 丢失即"票没有 run"，只能手写映射 | 2026-10-22 09:1x，三张 pw 票 |
| 4 | 环境靠借：worktree 无 `node_modules`，执行者把别的项目依赖做成 junction 借来用 | pw01 回执自述 |

## 2. 决策

### D1 Seat 是一等公民

- 一条 active run = 一个 seat；seat 属于 **Execution**，不是 Run 的历史属性。
- `dispatch seat` 报占用 / 上限 / 剩余，并列出可回收的 inactive 成员；满了就说"先回收或排队"，不让 `spawn` 去撞平台错误。
- 平台侧"inactive 应释放名额"另提需求单，技能只做规避。

### D2 Deadline 与 Sweep：只读巡检，不自动杀

- 派单方必须给 deadline（默认 15 分钟），写进 `run.json`。
- `dispatch sweep` 对每条 active run 报：**存活时长 / 最后一个产物距现在多久 / 是否已有回执**。三列都给人看，**不自动 kill**——自动 kill 会重演今天的误杀。
- 判活规则写进 SKILL：看**会话活动**（工具调用是否在增长），不看产物是否出现。

### D3 Repair：索引是缓存，run 目录是事实

- `dispatch repair` 从 `.dispatch/runs/*/run.json` 反向重建 `state.json`；默认 dry-run，`--write` 才落盘。
- 输出三分类：**新增 / 状态不一致 / 冲突**（index 与 disk 指向不同 run）。有冲突退出码 1，要人裁决。

### D4 环境契约：禁止借用，缺就 exit 2

- `render --env-hint "<命令>"` 把构建前置写进 `run.json` 与 work-order 的 **Environment prerequisites** 段。
- 执行者遇前置缺失：**exit 2 + 回执写"环境未就绪"**，不得借用其它项目依赖、不得静默跳过构建。
- 理由：借依赖会让"可复现"变成谎话，也会让回执里的 gzip 数字失去意义。

### D5 评审分档：L1 可自评但留痕，L2+ 必须异体

- L1：lead 可自评 `pass`，但必须记 `self-reviewed: true` 与理由，land 记录里可见。
- L2 及以上：必须另起 reviewer（人或独立会话），输入用 **review packet**（票据快照 + diff + 回执 + 验收证据的哈希冻结），不允许评审者直接读活动 worktree。

## 3. 后果

- 正面：派单可观测、状态可恢复、环境可复现、评审有分档。
- 负面：多两条命令要记；deadline 需要派单方主动给。
- 不解决：平台名额回收（D1 只是绕）、子 agent 探索期本来就慢（只能观测，不能催）。
