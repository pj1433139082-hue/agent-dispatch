# 项目术语

本文件维护 agent-dispatch 的领域词汇；规格与用法见 README，启动方案见 `tasks/kickoff/plan.md`，架构决策见 `docs/adr/`。

## 核心对象

**Ticket（票据）**:
一票一文件的 Markdown 事实源，声明目标、依赖、读写域、验收命令和风险等级；区别于自由文本任务。
_Avoid_: 任务卡、todo、issue（除非明确指 GitHub issue）

**Run（运行）**:
一次 `render` 产生的领取记录，绑定票据内容哈希；包含工单、回执、验收和评审证据。
_Avoid_: 执行、job、session

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

## 调度词汇

**Owner**:
票据声明的负责角色，用于阻止自审。
_Avoid_: assignee、执行人

**Write scope（写域）**:
票据允许改动的 git 相对路径或 glob；verify 以此判断改动是否越界。
_Avoid_: 修改范围、touch list

**Risk（风险等级）**:
L0–L4 的风险分级；v0.1 只在 L4 强制 `--human` 评审。
_Avoid_: priority、severity

**Wave（波次）**:
按 `blocked-by` 拓扑排序后同批可执行的票据集合；同波写域重叠会产生冲突提示。
_Avoid_: batch、stage

**Frontier**:
当前依赖已满足、可以立即领取的票据集合。
_Avoid_: backlog、queue

**Export（导出）**:
把 ready 票据转换到 DSH team、DSH board、Codex 或 generic 载荷；只读，不调用远端 API。
_Avoid_: sync、publish

## Rules

- 一个概念只保留一个主说法，其余写进 `_Avoid_`。
- 定义说明“是什么、区别于什么”，不写实现步骤。
- 术语与实际 CLI/README 冲突时，以可执行行为为准并同步改词条。
