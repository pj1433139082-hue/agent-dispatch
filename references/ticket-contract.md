# 票据与回执契约

## 票据

一张票一个 Markdown 文件，放在 `tickets/`，文件名建议 `<id>-<slug>.md`。

必填：

- 标题：`# <id>: <title>`
- `**What to build:**` 或 `## What to build`
- `**Blocked by:**`（无依赖写 `None`）
- `## Dispatch` 下的 `Write scope` 和 `Verify`
- `## Acceptance` 至少一条 `- [ ]`

可选：`Owner`、`Risk`、`Read scope`、`Status`。

状态机：

```text
ready -> claimed -> running -> review -> done
                     |           |
                     +-> failed <+
```

执行者只能写业务文件和 `receipt.json`，不能改票据状态；状态只能由 `verify` / `review` 推进。

## 回执

`receipt.json` 放在本次 Run 的目录，最小字段：

```json
{
  "ticket_id": "01",
  "run_id": "01-...",
  "status": "done",
  "summary": "做了什么",
  "evidence": ["evidence.txt"]
}
```

证据文件路径必须相对 Run 目录，不能是绝对路径。`verify` 会计算证据文件 sha256，并检查 git diff 是否全部落在 `Write scope` 内。

## 风险等级

- `L0`：只读。
- `L1`：普通 worktree 写入。
- `L2`：沙箱进程。
- `L3`：宿主/GPU 环境。
- `L4`：必须人工确认；`review` 必须加 `--human`。

风险等级目前主要映射到 DSH 卡片 permission；本地 `verify` 的强制差异点是 L4 的人工评审。
