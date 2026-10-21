# ADR 0005 — auto 只编排外部执行器，不接管验收与评审

- 状态：Accepted（用户 2026-10-21 批准“补”dispatch auto）
- 日期：2026-10-21
- 决策者：潘杰（用户）、lead
- 相关：`src/agent_dispatch/auto.py`、`src/agent_dispatch/cli.py`、`docs/verification/2026-10-21-v0.6-auto.md`

## 背景

v0.5 已有 render / start / verify / review / land 的完整手动门禁，但没有一条命令把“领取 → 外部执行 → 验收”串起来。用户希望半自动推进，同时保留独立验收和异体评审，不让自动执行变成自证。

## 决策

1. `dispatch auto <id> --executor <shell>` 只调用用户提供的 shell 命令；不内置模型客户端，也不绑定 DSH、Codex 或某个 agent SDK。
2. 执行器在 Run 的 worktree 中运行，业务文件写 worktree；`receipt.json` 与证据写 `DISPATCH_RUN_DIR`。执行器退出码不是验收结论，`verify` 仍是唯一验收门禁。
3. 默认 `--until review`：verify passed/degraded 后停在 review；degraded 仍需显式 `--accept-degraded`。
4. `--until land` 必须同时提供 `--reviewer` 和 `--reviewer-command`；reviewer 写入 `review-result.json`，只有退出码 0 且 verdict=pass 才记录 review 并 land。
5. land 仍只创建本地 integration branch；auto 不 push、不合并目标分支。
6. `--max-attempts` 重试复用同一个 Run/worktree，不重建 Run；每次尝试的日志、日志哈希和 verify 结论写入 `auto/attempt-NN.log` 与 `auto.json`。

## 备选方案

- 内置 CrewAI / LangGraph / SDK 运行时：引入依赖与执行器绑定，拒绝。
- auto 自己充当 reviewer：等于实现者自审，拒绝。
- auto 直接 push / 合并目标分支：越过人工 PR 审查，拒绝。

## 后果

- 执行器的能力与安全性由用户提供的命令决定；票据与执行器都应按受信任输入处理。
- 自动推进仍留下完整的 auto.json、verify.json、review.json、landing.json 与 ledger 证据链。
- 将来若加 DSH 执行器适配层，只作为 `--executor` 的一种命令实现，不改变本 ADR 的门禁边界。
