# 项目术语

本文件维护 agent-dispatch 的领域词汇；规格与用法见 README，启动方案见 `tasks/kickoff/plan.md`，架构决策见 `docs/adr/`。

## 核心对象

**Ticket（票据）**:
一票一文件的 Markdown 事实源，声明目标、依赖、读写域、验收命令和风险等级；区别于自由文本任务。
_Avoid_: 任务卡、todo、issue（除非明确指 GitHub issue）

**Run（运行）**:
一次 `render` 产生的领取记录，绑定票据内容哈希；包含工单、回执、验收和评审证据。
_Avoid_: 执行、job、session

**Execution（执行尝试）**:
一次外部执行端（DSH session、Codex、人工）对某个 Run 的实际尝试；一个 Run 可以有多条 Execution，失败重试不改变 Run 的领取事实。
_Avoid_: 运行、job、session

**Auto run（自动推进）**:
一次 `dispatch auto` 在同一个 Run 内调用外部执行器、跑 verify，并可按配置继续独立评审与 land；可带协议门禁（`--protocol full`：context / brief / checkpoint / closeout），但**不做多票编排**。执行器退出码不是验收结论。
_Avoid_: 全自动交付、自动验收、流水线

**Pipeline（多票编排）**:
按 `blocked-by` 拓扑把多张票排成波次并连续执行的能力。当前**不存在**，只是先占词；不要拿 Auto run 冒充 Pipeline。
_Avoid_: auto、批量派单

**Executor（执行器）**:
用户提供给 `dispatch auto` 的 shell 命令，在 Run 的 worktree 中写业务文件与回执；不是 dispatch 内置的模型运行时。
_Avoid_: agent、模型、worker

**Worktree（工作树）**:
某个 Run 独占的 git worktree 与分支；代码改动发生在其中，主仓工作区不作为执行根。
_Avoid_: 分支、目录、workspace（DSH workspace 是执行端概念）

**Work order（工单）**:
从票据渲染出的窄上下文执行说明，给执行者目标、读写域、验收命令和回执契约。
_Avoid_: 任务说明、prompt、handoff

**Receipt（回执）**:
执行者唯一可写的运行产物，声明做了什么和证据文件在哪；不能直接改票据状态。
_Avoid_: 完成报告、结果、summary

**Verify（验收）**:
独立门禁，复跑票据声明的命令、核对真实 git diff 是否越出写域，并给证据算哈希；通过才进入 review。
_Avoid_: 测试、检查、CI

**Review（评审）**:
异体复核门禁，评审者不能是票据 Owner 或实际领取人；通过才进入 done。
_Avoid_: 审批、code review（可指具体活动）

**Review packet（评审包）**:
一次 Review 的不可变输入集合：票据快照、diff、改动文件、回执、验收证据、基线 review guide 与哈希清单；评审者只读包，不读活动 worktree。
_Avoid_: 评审报告、review 结果

**Review guide（评审指南）**:
固定在 base commit 的评审标准文本；评审者以它为准，不读取被审 change 中可能被改写的规则文件。
_Avoid_: AGENTS.md、规范（泛称）

## 派单生命周期

**Seat（名额占位）**:
一条 active Run 占用一个执行端名额；inactive 成员在宿主侧仍占位，所以"派不出去"是名额问题，不是票据问题。
_Avoid_: 槽位、并发数、worker 数

**Deadline（派单时限）**:
派单方给一次执行约定的最长时限（默认 15 分钟）；到点先 `sweep` 看活动，再决定是否收回。
_Avoid_: 超时、timeout（那是命令级参数）

**Sweep（只读巡检）**:
对 active Run 报"存活时长 / 最后产物距现在多久 / 是否已有回执"的只读报告；不自动 kill。
_Avoid_: 监控、watchdog（本项不做自动处置）

**Repair（索引重建）**:
从 `.dispatch/runs/*/run.json` 反向重建 `state.json` 的幂等操作；默认 dry-run，冲突要人裁决。
_Avoid_: 修复、恢复（易与回滚混淆）

**Self-reviewed（自评标记）**:
L1 票据允许 lead 自评通过时留下的痕迹，land 记录里必须可见；L2 及以上不得使用。
_Avoid_: 免评审、跳过评审

## 框架边界

**Framework project（框架项目）**:
由 agent-workflow-framework 纳管的项目工作区，含 `project.json`、`tasks/<task-id>/` 与 `.agent-workflow.local.json`；承载项目身份与启动规划事实，不承载票级执行状态。
_Avoid_: dispatch 项目、仓库（泛称）

**Framework task（框架任务）**:
`tasks/<task-id>/task.json` 记录的启动规划任务；阶段只表示 scope → plan → ready，ready 不等于项目实现完成。
_Avoid_: ticket、Run（dispatch 的执行对象）

## 调度词汇

**Owner**:
票据声明的负责角色，用于阻止自审。
_Avoid_: assignee、执行人

**Write scope（写域）**:
票据允许改动的 git 相对路径或 glob；verify 以此判断改动是否越界。
_Avoid_: 修改范围、touch list

**Risk（风险等级）**:
L0–L4 的风险分级；v0.2 只在 L4 强制 `--human` 评审，并映射到 DSH 卡片的 permission。
_Avoid_: priority、severity

**Wave（波次）**:
按 `blocked-by` 拓扑排序后同批可执行的票据集合；同波写域重叠会产生冲突提示。
_Avoid_: batch、stage

**Frontier**:
当前依赖已满足、可以立即领取的票据集合。
_Avoid_: backlog、queue

**Export（导出）**:
把 ready 票据转换到 DSH team、DSH board、Codex 或 generic 的离线载荷；只读，不调用远端 API。
_Avoid_: sync、publish

**DSH Push（投递）**:
把 ready 票据的 create 信封发到本机 DSH 看板 API，建立可追踪的卡；只建卡，不运行卡。
_Avoid_: 自动执行、自动派活

**External outcome（外部结果）**:
外部 agent 完成工作后写回 DSH 看板执行记录的结果；它是看板事实，不是本项目的验收结论。
_Avoid_: verify、验收通过

**Recovery point（恢复点）**:
某个 Run 在关键门禁处生成的不可变恢复快照；包含状态、运行证据、票据快照、代码 patch/bundle 与哈希清单，用于 restore 或审计。
_Avoid_: 备份文件、snapshot（泛称）

**Landing（落地记录）**:
一次把已验证 Run 合入本地 integration branch 的记录，声明 target / run / landing commit 与 `pushed=false`；不 push、不合并目标分支，回退以新的 revert 记录表达，不重写共享分支历史。
_Avoid_: merge、发布

## Rules

- 一个概念只保留一个主说法，其余写进 `_Avoid_`。
- 定义说明“是什么、区别于什么”，不写实现步骤。
- 术语与实际 CLI/README 冲突时，以可执行行为为准并同步改词条。
