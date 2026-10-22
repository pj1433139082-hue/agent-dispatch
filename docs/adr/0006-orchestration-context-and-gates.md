# ADR-0006 编排协议：上下文包 + 两阶段 brief + 检查点回灌，执行端以子智能体/Agent Team 为主

- 状态：Accepted（2026-10-22）
- 触发：2026-10-21 会话 f85c01f1。用户实测「看板派单跑得很差」：会话与会话之间没有上下文、auto 模式子智能体跑偏、没有"一收到消息就审核"的对齐点。用户结论：**看板不放进框架技能，用子智能体 + Agent Team 就够**。
- 影响范围：`src/agent_dispatch`（context / brief / feedback 三个新增模块 + render/auto 接线）、`SKILL.md`。

## 1. 问题（三条，来自实跑复盘）

| # | 缺口 | 具体表现 |
|---|---|---|
| 1 | 卡片没有上下文载体 | `card_input()` 只把 `ticket_section()` 塞进新会话 prompt；项目入口文档、前序决策、相关文件、上次运行结果都不带。每张卡"只拿到票面就开工" |
| 2 | 开工前没有对齐 | `auto_run()` 是"建 worktree → 直接执行 → 最后 verify"，执行端没有先回报"我理解的目标 / 计划 / 要改哪些文件 / 风险 / 疑问" |
| 3 | 过程无审核点、失败不回灌 | `max_attempts` 只是原样重跑同一条命令；上一轮 `verify_errors` 不进下一轮；reviewer 默认不跑 |

## 2. 技术选型（先看别人怎么做）

| 来源（本机副本） | 做法 | 可借鉴 | 不采用 |
|---|---|---|---|
| gstack `lib/owner-brief.ts` + `bin/gstack-owner-brief` | 计划门给 owner 看一页 brief：纯语言摘要 + `## URGENT, outside this plan` + 编号决策（`auto` 项给出默认值、`approval` 项等待回答），完整评审留在 `review-record.md` | **brief 的字段结构**（理解/计划/决策/待确认）与"brief 指向详细记录，不复制" | 它的 gate-list 页大小、决策 id 体系（对我们过重） |
| gstack `lib/autoplan-checkpoint.ts` | 每次状态落定发布一份**不可变 generation**：`checkpoint.json`（逐文件 sha256）+ 运行文件 + `restore.md`；`current.json` 一次 rename 切换；旧 generation 保留到切换提交；加锁；不允许新 generation 覆盖更新的 | **检查点 = 带哈希的只追加快照 + 恢复说明**；"中断即回退到上一代" | Drive 目录、voice/phase 绑定（与本仓无关） |
| get-shit-done `src/gate-tdd-review-checkpoint.cts` | 门禁模块统一返回 `GateResult{passed, block, ...}`，advisory 检查也可用同一形状，宿主循环只读一个字段 | **门禁结果统一契约**（passed/block/findings），advisory 与 blocking 同形 | 它的 plan/frontmatter 体系 |
| ruflo `plugins/ruflo-swarm`、`scripts/loop-checkpoint.mjs` | swarm 编排 + 循环级 checkpoint | 循环级快照的概念 | 引入其运行时（与本仓"零第三方依赖 CLI"冲突） |
| Temporal / Dagster / LangGraph | 外部工作流引擎：持久化状态机、重试策略、事件历史 | 语义参考（checkpoint、retry-with-feedback） | **采纳会引入服务端依赖**，违反 ADR-0001 文件优先 |

**选型结论**：不引入外部编排引擎；在既有文件契约上补齐三个语义——(A) 上下文包、(B) 两阶段 brief 门、(C) 失败回灌、(D) 收口一致性评审。参考实现只借**形状**（brief 字段、generation 快照、GateResult 契约），不搬代码。

## 3. 决策

### D1 执行端：子智能体 / Agent Team 为默认，DSH 看板降为可选投递端

看板仍是"跨会话落库 + 人肉点运行"的手段，但**不再作为框架技能的主路径**；`dsh push` 保留（向后兼容），`SKILL.md` 的默认流程改为 render → 子智能体/Agent Team 执行 → verify → review。

### D2 Context Pack（已实现）

`dispatch context <id>` 生成 `.dispatch/context/<id>.md`：票面框架、目标、写/读域、完成定义、**项目入口文档摘录**（AGENTS.md / CLAUDE.md / CONTEXT.md 前 60 行）、**同票历史运行**（state / verify 状态 / error）、**阻塞邻居**（依赖票标题与状态）、**踩坑笔记索引**。只读、确定性、不调模型。`render --with-context` 把它写进 run 目录并附到 work-order。

### D3 两阶段 brief（已实现）

`dispatch brief <id>` 生成只读 brief 模板（理解的目标 / 计划 / 准备改动的文件 / 风险 / 疑问）；`--check` 校验五段非空且非占位；`--approve <人>` 记录审批（含 brief 与票据的 sha256）。`render --require-brief` 在无有效审批时拒绝开局；brief 或票据在审批后被改动即失效。

### D4 失败回灌（已实现）

第 n>1 次尝试前，把第 n-1 次的 `verify_errors` 写成 `.dispatch/runs/<run>/auto/feedback-<n-1>.md`，并通过 `DISPATCH_FEEDBACK` 传给执行端；`attempts[]` 记录该路径。不再"原样重跑"。

### D5 门禁结果统一形状（沿用现实现，不重写）

`verify` 已输出 `status/errors`；后续 checkpoint 与 closeout 都走同一 record 形状，避免每个门一套字段。

## 4. 后果

- 正面：新会话拿到的是"票面 + 项目事实"而不是只有票面；写代码前有被审核的一次机会；重试带方向。
- 负面：每票多一个 `.dispatch/context/<id>.md` 与 `.dispatch/briefs/<id>.md`；brief 是人工/lead 的一次额外动作，票多时是成本。
- 边界：本 ADR 不改变 `auto` 的默认行为（brief 门需 `--require-brief` 显式开启），不删任何看板代码。
