# 票据与回执契约

## 票据

一张票一个 Markdown 文件，放在 `tickets/`，文件名建议 `<id>-<slug>.md`。

必填：

- 标题：`# <id>: <title>`
- `**What to build:**` 或 `## What to build`
- `**Blocked by:**`（无依赖写 `None`）
- `## Dispatch` 下的 `Owner`、`Risk`、`Write scope`、`Verify`
- `## Acceptance` 至少一条 `- [ ]`

可选：`Read scope`、`Status`、`Persona`。

`Persona` 写相对票据目录的人设文件路径或短名。`dispatch assign` 会复制源文件到 `tickets/personas/`、写入票据，并追加 `.dispatch/assignments.jsonl`；`personas list` 用于发现候选。解析失败会让 `lint` 报 `invalid_persona`。票据契约优先于人设：写域、Acceptance、Verify 冲突时以票据为准。

`Verify` 命令按当前平台 shell 执行（Windows 为 `cmd.exe`，其他平台为 `/bin/sh`），支持 `&&`、管道、带引号的参数和 Windows 反斜杠路径；每条命令都必须能从 execution root 独立复跑。

状态机：

```text
ready -> claimed -> running -> review -> done
                     |           |
                     +-> failed <+
```

执行者只能写业务文件和 `receipt.json`，不能改票据状态；状态只能由 `verify` / `review` 推进。`failed` 票据可重新 `render` 重试，并会继续出现在 `status` / `export` 的可重试 frontier 中。

## Worktree 与执行根

`render` 默认在 `.dispatch/worktrees/<run-id>` 创建独立 git worktree，分支为 `dispatch/<run-id>`，并把 `execution_root` 写进 `run.json`。执行者必须在 execution root 里写业务文件；verify 也在那里跑命令和算 git diff。

- `--no-worktree` 是逃生口：`run.json` 不写 worktree 字段，执行根回退为主仓。
- 旧版 run.json 没有 `execution_root` 时，按主仓执行，保持向后兼容。
- verify 除检查 execution root 的 diff 外，还会检查 main checkout 在 base commit 之后是否被改动；主仓有业务改动会直接失败。

## 回执

`receipt.json` 放在本次 Run 的目录。v0.5 起使用判据级回执：

```json
{
  "ticket_id": "01",
  "run_id": "01-...",
  "status": "done",
  "summary": "做了什么",
  "criteria": [
    {
      "id": 1,
      "verdict": "pass",
      "note": "可选的说明",
      "evidence": [
        {"kind": "file", "path": "evidence/proof.txt", "sha256": "<可选>"},
        {"kind": "inline", "content": "expected output\n", "sha256": "<可选>"},
        {"kind": "absent", "path": "src/old.py"},
        {"kind": "command", "command": "python -m pytest -q", "exit_code": 0},
        {"kind": "note", "note": "人工核对过"}
      ]
    }
  ]
}
```

规则：

- `criteria` 必须正好覆盖 `## Acceptance` 的每一项：id 为 `1..N`，不能缺、不能多、不能重复。
- 每个 criterion 至少一条 evidence；`verdict` 只能是 `pass` 或 `fail`。
- 证据路径相对 Run 目录，不能是绝对路径。
- `file`：文件必须存在；带 `sha256` 就核对，不带则记录实际哈希。
- `inline`：字面内容；带 `sha256` 就核对。
- `absent`：该路径必须不存在。
- `command`：执行者报告的命令与退出码；verify 不复跑，但 `exit_code` 必须为 0。
- `note`：只有陈述，没有可复算物证。一个 criterion 如果只有 note 证据，会把该 criterion 记为 attested。

结论：

- `passed`：所有 criterion 都有可复算证据且全部 pass。
- `degraded`：没有 fail，但至少一个 criterion 只有 note 证据；可进入 review，但必须 `review --accept-degraded`。
- `failed`：任何 criterion fail、证据校验失败、命令复跑失败、写域越界或主仓污染。

`dispatch verify` 退出码：0 = passed，2 = degraded，1 = failed。

## 复核记账

`review` 成功后写 `review.json`，并向 `.dispatch/ledger/reviews.jsonl` 追加一行。行内包含 `at`、`ticket_id`、`run_id`、`reviewer`、`verdict`、`notes`、`verify_status`、`accepted_degraded`、`review_hash`。ledger 是 append-only 的审计记录，不能代替 `review.json`。

## 自动执行

`dispatch auto <id> --executor <shell>` 会创建 Run 与 worktree，在 worktree 中运行执行器命令，然后调用与手动流程相同的 `verify`。执行器收到：

- `DISPATCH_TICKET_ID`、`DISPATCH_RUN_ID`、`DISPATCH_RUN_DIR`、`DISPATCH_EXECUTION_ROOT`、`DISPATCH_WORK_ORDER`、`DISPATCH_TICKET_PATH`、`DISPATCH_ATTEMPT`。
- 业务文件写在 `DISPATCH_EXECUTION_ROOT`；`receipt.json` 和证据写在 `DISPATCH_RUN_DIR`。

执行器的退出码不是验收结论；verify 仍复跑票据命令、检查写域与证据。`--max-attempts` 控制失败重试，每次尝试的日志与结果写 `auto.json`。

`--until land` 时必须提供独立的 `--reviewer` 和 `--reviewer-command`。reviewer 额外收到 `DISPATCH_REVIEWER`、`DISPATCH_VERIFY_JSON`、`DISPATCH_REVIEW_RESULT`，并把 `{"verdict":"pass"|"fail","notes":"..."}` 写到 `DISPATCH_REVIEW_RESULT`；只有退出码 0 且 verdict=pass 才会记录评审并 land。

## 落地

`dispatch land <id>` 只接受已 `done` 且 review 通过的 worktree Run；默认目标分支 `main`（否则 `master`/当前分支），默认 integration branch `dispatch/land/<run-id>`。

- 只创建本地 integration branch；不 push、不切换、不合并目标分支。
- 写 `landing.json` 到 Run 目录，并追加 `.dispatch/ledger/landings.jsonl`；`pushed=false`、`pr_url=null`。
- land 会先核对 `verify.json` 的 `diff_hash`；review 后 worktree 再被修改会拒绝，必须重新 verify/review。
- 冲突时清理临时 worktree 与 integration branch，目标分支保持原样。

## 风险等级

- `L0`：只读。
- `L1`：普通 worktree 写入。
- `L2`：沙箱进程。
- `L3`：宿主/GPU 环境。
- `L4`：必须人工确认；`review` 必须加 `--human`。

风险等级目前主要映射到 DSH 卡片 permission（兼容层）；本地 `verify` 的强制差异点是 L4 的人工评审。
