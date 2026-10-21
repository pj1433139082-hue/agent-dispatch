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

## 实测记录

2026-10-21 用 `TaskBoardClient` 创建父卡/子卡，显式 POST `{kind:"run", taskId:<parent>}`：

- 父卡与子卡最终 `status=done`、`result=succeeded`；
- 父卡 execution 摘要包含 `PARENT_PROBE_OK` 与 `CHILD_PROBE_OK`，证明 Host 实际 spawn 了 teammate；
- 探针卡已先删子卡、再删父卡，`remaining=[]`。

## 已知怪癖

- `record-external-outcome` 会把 `summary` 写进执行记录的 `error` 字段，即使 `result=succeeded`；回读时以 `result`/`external` 为准。
- 删除父卡前必须先删除或解除子卡，否则返回 `task has subtasks; detach or delete them first`。
- `dsh push` 只建卡，不运行；运行需要显式 action 或人工点击。
