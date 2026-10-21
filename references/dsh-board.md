# DSH 看板接口与边界

## 端点

默认：`http://127.0.0.1:50567/api/task-board`

- `GET /state`
- `GET /events`（SSE）
- `POST /action`

请求要求同源标记 `sec-fetch-site: same-origin`，Host/Origin 为 loopback；POST body 上限 64KiB。

## 卡片

`create` action 的 `input` 至少包含：

```json
{
  "title": "...",
  "description": "...",
  "prompt": "...",
  "permission": "read-only",
  "tags": []
}
```

团队模式：父卡 `teamRun: true`，每张票一张 `parentId` 指向父卡的子卡。运行父卡时 Host 会启动 Lead session，并为直接子卡 spawn teammate。子卡可以继承父卡的 workspace/mode/permission/model。

## 卡片变更 action

`POST /action` 的 `action` 只接受下列信封。不要给 `update` 传 `id` / `input`，也不要给 `archive` / `delete` 传额外字段。

更新卡片（`patch` 必须是非空 JSON object）：

```json
{
  "kind": "update",
  "taskId": "<task-uuid>",
  "patch": {
    "title": "新标题",
    "description": "补充说明",
    "prompt": "新的提示词"
  }
}
```

归档卡片（只设置 `archivedAt`，不删除）：

```json
{"kind": "archive", "taskId": "<task-uuid>"}
```

删除卡片（物理删除）：

```json
{"kind": "delete", "taskId": "<task-uuid>"}
```

边界：

- 三个 action 都用 `taskId` 标识目标卡片；`update` 另带非空 `patch`。卡片 id 由 `project` + 票据 id 确定性生成，或由 `dsh push` 写入映射后读取。
- `update` 返回最新看板快照，CLI 会回读 `title` / `status`。
- `archive` 不是删除；归档后卡片仍可用 id 查到。
- `delete` 遇到有子卡的父卡会返回 `task has subtasks; detach or delete them first`；先删除或解除子卡，再删父卡。
- 这些 action 只改看板，不改本地票据状态；验收仍由 `dispatch verify` / `review` 决定。

## 实测记录

2026-10-21 用 `TaskBoardClient` 创建父卡/子卡，显式 POST `{kind:"run", taskId:<parent>}`：

- 父卡与子卡最终 `status=done`、`result=succeeded`；
- 父卡 execution 摘要包含 `PARENT_PROBE_OK` 与 `CHILD_PROBE_OK`，证明 Host 实际 spawn 了 teammate；
- 探针卡已先删子卡、再删父卡，`remaining=[]`。
- 2026-10-21 用 `dispatch dsh push` 创建一张探针卡，随后 `dsh update`（改 title/description/prompt）、`dsh archive`（回读 `archivedAt`）、`dsh delete` 依次成功；删除后按 task id 查看看板，`remaining=0`。

## 已知怪癖

- `record-external-outcome` 会把 `summary` 写进执行记录的 `error` 字段，即使 `result=succeeded`；回读时以 `result`/`external` 为准。
- 删除父卡前必须先删除或解除子卡，否则返回 `task has subtasks; detach or delete them first`。
- `dsh push` 只建卡，不运行；运行需要显式 action 或人工点击。
