# ADR 0002 — DSH 看板走本机 loopback HTTP，验收仍在本地

- 状态：已采纳
- 日期：2026-10-21
- 相关：`dsh.py`、`docs/project/architecture.md`

## 背景

v0.1 的 `dsh-board` 只生成裸卡 JSON，需要人工粘贴到 DSH。DSH 的 Team 任务板没有对外直接改任务的 REST；任务看板插件（`@linxin666/dsh-client-ui-task-board`）则提供同源 HTTP 入口：

- `GET /api/task-board/state`
- `POST /api/task-board/action`

`POST /action` 接受 `TaskBoardActionEnvelope`，其中 `create` 可建卡，`record-external-outcome` 可把外部 agent 的结果写进执行记录。该入口要求 loopback + 同源标记，适合本机 CLI 使用，不需要模型调用。

## 决策

1. `dispatch dsh push` 只做 `create`，不调用 `run`。运行卡片仍是人在 DSH GUI 中的明确动作。
2. 卡片 id 由 `project` + 票据 id 确定性生成（UUIDv5），重复 push 以看板 state 去重。
3. `dispatch dsh outcome` 只调用 `record-external-outcome`，把外部执行结果写进看板；它不改变本地票据状态，也不替代 `dispatch verify`。
4. 映射保存在 `.dispatch/dsh-map.json`，不提交 Git。
5. `dsh-board` 文件导出改为完整的 `create` 信封文档，便于人工检查或由其他工具投递。

## 后果

- 需要 DSH Desktop 正在运行；端口可用 `--url` 或 `DSH_TASK_BOARD_URL` 覆盖。
- 该 HTTP 入口属于本机插件接口，不是稳定的公共 API；DSH 升级后需重跑真实投递探针。
- 看板上的 `done` 只是执行记录，不是本项目的验收结论；票据进入 `done` 仍必须经过 `verify` 和 `review`。
- 团队模式创建一张 `teamRun` 父卡和每票一张直接子卡；是否真的启动 Agent Team 仍由看板的运行动作决定。
