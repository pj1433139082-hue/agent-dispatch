# ADR 0003 — 框架项目管启动事实，dispatch 管票级执行

- 状态：Proposed（待用户确认）
- 日期：2026-10-21
- 决策者：lead
- 相关：`project.json`、`.agent-workflow.local.json`、`tasks/kickoff/`、`docs/project/progress.md`

## 背景

`agent-dispatch` 本身已经是一个 agent-workflow-framework 项目：

- `project.json` 声明 `project_id=agent-dispatch`；
- `.agent-workflow.local.json` 指向框架目录 `E:/beikong-code/agent-workflow-framework`，任务为 `kickoff`；
- `tasks/kickoff/task.json` 为 `project-planning / assisted / ready`，`plan-acceptance` 已由用户潘杰签署，`pending_decisions=[]`，`completed_locally=true`。

框架 v0.1 的边界是：一个工作区只有首个任务，阶段线性推进，不支持向既有工作区追加任务；`ready` 只表示启动规划有效，不表示业务实现或部署完成。dispatch 则需要并行票据、依赖波次、每次 Run 的独立验收与评审，二者不是同一种状态机。

## 决策

1. 框架项目是项目身份与启动规划的事实源；dispatch 只读 `project.json`、`.agent-workflow.local.json` 和 `tasks/<task-id>/task.json`，不写框架任务事实或 `workflow-state.json`，也不推进框架阶段。
2. dispatch 的票级状态继续只存在于 `.dispatch/state.json` 与 `.dispatch/runs/<run-id>/`；不把 ticket 状态镜像成框架任务阶段，避免第二套状态机。
3. v0.4 继续在现有 `agent-dispatch` 工作区的 `kickoff` 项目下实现；不新建框架工作区，不另造 task-id。框架任务保持 `ready`，这是启动规划的真实状态，不是实现未完成的冒充。
4. `dispatch status --json` 可以增加只读的 `framework` 块（`project_id`、`task_id`、`stage`），但必须标注为只读投影，不能据此推进或回写框架。
5. 实施进展只作为人类可读事件写入 `docs/project/progress.md`；需要交接时由人决定是否更新项目文档，不自动改任务。
6. Matt 流程产出的 `.scratch/<feature>/issues/*.md` 仍是 dispatch 票据的主要导入源；框架 `tasks/<task-id>/plan.md` 的“可执行任务”只可作为候选，不自动变成票据。
7. 未来框架若支持多任务，再增加可选的框架任务适配；v0.4 不把“一个项目多任务”硬编码进 dispatch。

## 后果

- 优点：项目身份、启动决定、票级执行证据各自有唯一事实源；不会出现“框架任务完成”和“票据完成”互相冒充；现有仓库、PR、CI 与已签的 kickoff 记录都不需要重写。
- 代价：框架 `status` 在实现阶段仍显示 `ready/completed_locally=true`，需要读者理解这是启动规划状态；dispatch 需要在自己的状态输出里提供项目身份投影，减少误读。
- 边界：如果用户要求把 v0.4 作为独立的框架项目或新任务，必须另建工作区或等框架提供追加任务能力，不能在现有 `tasks/kickoff` 上手工复制一份。
