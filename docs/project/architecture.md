# 项目架构

本页记录当前模块边界与数据流（v0.9；文档同步于提交 `6f46845`）；术语见 `CONTEXT.md`，关键决策见 `docs/adr/`。

## 模块与边界

| 模块 | 职责 | 边界 |
|---|---|---|
| `ticket.py` | 解析一票一文件的 Markdown，校验字段、依赖、写域和验收项 | 纯函数；不读写运行状态 |
| `graph.py` | 依赖图拓扑分波、环检测、同波写域重叠判断 | 纯函数；不执行命令 |
| `state.py` | `.dispatch/state.json` 与 Run 元数据；记录 base commit、票据哈希和状态 | 状态只能由 CLI 门禁命令推进 |
| `workorder.py` | 把票据渲染成 `work-order.md` | 只生成文本，不写业务文件 |
| `verify.py` | 复跑验收命令、检查 git diff 写域、证据 sha256 | 不修改票据；拒绝时写 verify.json |
| `review.py` | 异体评审与 final verdict | 拒绝自审；L4 必须人工 |
| `landing.py` | 把已验证 Run 合入本地 integration branch，写 landing ledger | 不 push、不切换、不合并目标分支 |
| `auto.py` | 调用外部执行器，串联 render → 执行 → verify，支持重试与可选独立评审/land | 不内置模型；不绕过 verify/review |
| `export.py` | 把 ready 票据导出为 dsh-team / dsh-board / codex / generic | 只读；不调用远端 API |
| `persona.py` | 发现、解析、写入 agent 人设；`assign` 复制到 `tickets/personas/` 并记 assignments | 只改票据 Persona 行；票据已领取后拒绝 |
| `brief.py` | 两阶段的第一阶段：brief 模板、非空非占位校验、审批记录（brief 与票据 sha256） | 只读产物；不改代码；票据或 brief 变动即失效 |
| `context.py` | 生成上下文包：票面框架、入口文档摘录、同票历史运行、阻塞邻居、踩坑索引 | 只读、确定性；不调模型、不联网 |
| `feedback.py` | 把上一次 verify 失败原因写成 `auto/feedback-<n-1>.md` 并注入执行环境 | 只写 Run 目录；不改变重试次数语义 |
| `checkpoints.py` | 为 Run 发布不可变检查点（代次目录、manifest、diff、恢复说明），原子替换 current.json | 只读源工作树；不删除旧代次 |
| `closeout.py` | 票据 / brief 声明文件 / 实际 diff 三方对照，写收口报告 | 只读证据；不推进票据状态 |
| `align.py` | 需求问卷（quick/standard/thorough）、spec 骨架、按交付标准切草稿票 | 只写 `docs/questions`、`docs/specs`、`.dispatch/drafts`；不代替思考 |
| `dsh.py` | 生成 DSH 看板信封、投递/触发/读回/变更本机 loopback 卡片、回写外部结果 | 只操作看板；不替代 verify |
| `cli.py` | argparse 命令路由、退出码和用户可见错误 | 不绕过各模块门禁 |

运行时只依赖 Python 标准库；pytest 仅为开发依赖。

## 输入与数据流

```text
tickets/*.md
  -> ticket.parse / lint
  -> graph.build_plan（波次、frontier、写域冲突）
  -> workorder.render（创建 .dispatch/runs/<run-id>/work-order.md）
  -> 执行者写业务文件 + receipt.json + 证据文件
  -> verify.verify_run（命令、diff、哈希）
  -> review.submit_review（异体裁决）
  -> landing.land_run（本地 integration branch，人工开 PR）
  -> state: done / failed

auto: ticket -> Run/worktree -> 外部执行器 -> verify（可重试）
  -> 默认停在 review；--until land 需独立 reviewer -> landing

两阶段：brief（只读，人工审批，记 sha256）
  -> render --require-brief（无有效审批拒绝开局）
  -> 实现 -> verify -> closeout（票据 / brief / diff 三方对照）-> review

上下文：context 命令或 render --with-context
  -> .dispatch/context/<id>.md（入口文档 / 历史运行 / 阻塞邻居 / 踩坑索引）

检查点：checkpoint 命令 -> .dispatch/runs/<run-id>/checkpoints/<代次>/（不可变）

ready tickets
  -> export.py（dsh-team / dsh-board / codex / generic，只读）
  -> dsh.py dsh push（看板 create 信封；只建卡不运行）
  -> dsh.py dsh outcome（外部执行结果回写；不替代 verify）
```

机器事实源是 `.dispatch/state.json`、`.dispatch/runs/<run-id>/` 与 `.dispatch/dsh-map.json`；票据文件本身保持只读，避免执行者改票自证。`verify` 会比对票据内容哈希，票据在 render 后被改动会使旧 run 失效。

## 关键决策入口

- `docs/adr/0001-file-first-cli.md`：文件优先、门禁命令独占状态推进。
- `docs/adr/0002-dsh-loopback-push.md`：DSH 看板只作为投递与回读面，验收仍由本地门禁负责。
- `docs/adr/0003-framework-project-boundary.md`：框架项目管启动事实，dispatch 管票级执行。
- `docs/adr/0004-collab-runbook-consolidation.md`：退役 runbook，dispatch 成为唯一票级入口。
- `docs/adr/0005-auto-execution.md`：auto 只编排外部执行器，验收与评审仍由本地门禁负责。
- `docs/adr/0006-orchestration-context-and-gates.md`：上下文包、两阶段 brief、失败回灌与收口的选型（借形不引引擎）。
- `docs/adr/0007-pipeline-ask-matt-five-stages.md`：五段主流程（需求对齐 → 拷问+选型 → 规格 → 拆票 → 实现）。
- `tasks/kickoff/plan.md`：v0.1 技术选择、风险与验收方法。
