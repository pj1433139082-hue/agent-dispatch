# ADR 0001: 文件优先、门禁命令独占状态推进

- 状态：Accepted
- 日期：2026-10-21
- 决策者：lead（项目启动阶段代签）

## Context

多智能体协作中，执行者容易自己宣布完成，票据、运行状态和证据散落在聊天或数据库里，无法用 git 审计。v0.1 需要一个人和多个 agent 都能读、能 diff、能复跑的最小闭环。

## Decision

1. 票据是一票一文件的 Markdown，作为需求、依赖、写域和验收的唯一事实源。
2. 运行状态与证据写入 `.dispatch/state.json` 和 `.dispatch/runs/<run-id>/`，JSON 为机器事实源。
3. 执行者只写 `receipt.json` 和业务文件；票据状态只能由 `verify` / `review` 命令推进。
4. `verify` 复跑票据声明的命令、检查 git diff 写域、核对证据 sha256；`review` 拒绝自审。
5. 导出只读 ready 票据，不调用远端 API。

## Consequences

- 优点：git 可审计、agent 可用窄上下文、无需数据库、跨 Windows/Linux。
- 代价：没有 Web UI 和多用户权限；管理员可直接改文件或绕过检查；运行状态不是防篡改存储。
- 后续若接入远端执行器，应保持票据契约和门禁语义不变，只替换执行与回传适配层。
