# 项目架构

本页记录 v0.1 的实际模块边界与数据流；术语见 `CONTEXT.md`，关键决策见 `docs/adr/`。

## 模块与边界

| 模块 | 职责 | 边界 |
|---|---|---|
| `ticket.py` | 解析一票一文件的 Markdown，校验字段、依赖、写域和验收项 | 纯函数；不读写运行状态 |
| `graph.py` | 依赖图拓扑分波、环检测、同波写域重叠判断 | 纯函数；不执行命令 |
| `state.py` | `.dispatch/state.json` 与 Run 元数据；记录 base commit、票据哈希和状态 | 状态只能由 CLI 门禁命令推进 |
| `workorder.py` | 把票据渲染成 `work-order.md` | 只生成文本，不写业务文件 |
| `verify.py` | 复跑验收命令、检查 git diff 写域、证据 sha256 | 不修改票据；拒绝时写 verify.json |
| `review.py` | 异体评审与 final verdict | 拒绝自审；L4 必须人工 |
| `export.py` | 把 ready 票据导出为 dsh-team / dsh-board / codex / generic | 只读；不调用远端 API |
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
  -> state: done / failed
```

机器事实源是 `.dispatch/state.json` 与 `.dispatch/runs/<run-id>/`；票据文件本身保持只读，避免执行者改票自证。`verify` 会比对票据内容哈希，票据在 render 后被改动会使旧 run 失效。

## 关键决策入口

- `docs/adr/0001-file-first-cli.md`：文件优先、门禁命令独占状态推进。
- `tasks/kickoff/plan.md`：v0.1 技术选择、风险与验收方法。
