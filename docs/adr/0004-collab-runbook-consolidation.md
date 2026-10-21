# ADR 0004 — 退役 agent-collab-runbook，agent-dispatch 成为唯一票级入口

- 状态：Accepted（用户 2026-10-21 选择“直接退役，按推荐来”）
- 日期：2026-10-21
- 决策者：潘杰（用户）、lead
- 相关：`docs/adr/0003-framework-project-boundary.md`、`agent-collab-runbook` 技能、`verify.py`、`review.py`

## 背景

`agent-collab-runbook` 与 `agent-dispatch` 在票级执行上约 60–70% 重叠：

| 能力 | agent-collab-runbook | agent-dispatch v0.4 |
| --- | --- | --- |
| 一卡一 worktree | 有（`card/<卡号>`） | 有（一 Run 一 worktree） |
| 工作集 / 写域 | 有（workset + git 差分） | 有（Write scope + git diff） |
| 回执 / 证据 | 两件套 + 判据级物证 | receipt criteria + 可复算物证 |
| 独立复核 | `verify_receipt.py` PASS/FAIL/DEGRADED | `verify` + `review` 门禁 |
| 落地 | 本机 `land`（ff/cherry-pick） | 设计为 integration branch + 人工 PR；v0.4 P0 尚未实现 `dispatch land` |
| 看板 / 交接区 | BOARD/PLAN/LOG | DSH 卡 + 本地状态 |
| 排班 / 唤醒 | dsh-cron + knock | 不建常驻调度器 |
| 租约 / 预算 / 轮转 | 有 | 无 |
| 依赖波次 / 票据 lint | 无 | 有 |
| 恢复点 / 回退 | 无 | 有 |

关键冲突：runbook 的 `land` 直接改本机主检出；dispatch v0.4 只创建 integration branch，由人工开 PR。两者不能在同一项目混用。

## 决策

1. **单一票级契约**：agent-dispatch 成为票据、Run、回执、验收、评审、落地的唯一执行契约；runbook 的 `BOARD.md` 卡不再作为第二套任务事实源。
2. **合并 P0 能力**：一票一 worktree、写域严格差分、判据级证据（file/inline/absent/command/note）、PASS/FAIL/DEGRADED 语义、复核记账，进入 dispatch 的 verify/review 设计。
3. **landing 以 v0.4 为准**：dispatch 的 landing 设计为只创建 integration branch 并交人工开 PR；不自动 push、不自动 merge；回退用 `git revert` 生成回退提交，绝不对共享 main 做 `reset --hard`。v0.4 P0 只锁定这条约束，尚未实现 `dispatch land` 命令；实现前落地由人工完成。
4. **不保留 P2 可选层**：排班、唤醒、租约、预算、会话轮转不并入 dispatch，也不继续由 runbook 承载；runbook 直接退役。需要排班时使用 DSH 原生看板 / Agent Team 能力，不在 dispatch 内建调度器、消息总线或常驻服务。
5. **退役顺序**：先把 P0 能力通过测试与跨项目 e2e，再从 skillshare 卸载 runbook；卸载后 `skillshare sync`。历史只保留源码仓库 tag，不保留可调用技能。
6. **不复制实现**：runbook 的 PowerShell/`_handoff` 代码不搬进 dispatch；只吸收契约语义和测试用例，保持 dispatch 的 Python 标准库边界。

## 后果

- 优点：票据执行只有一个入口；回执证据从“文件存在”提升到“判据级可复算”；不需要维护两套 worktree/verify/land 逻辑。
- 代价：runbook 的交接区、排班、租约能力不再可用；需要这些能力的场景改由 DSH 原生看板/Agent Team 承担。
- 边界：本 ADR 不承诺 agent-dispatch 提供会话排班、唤醒或租约；它只负责票级执行与门禁。
