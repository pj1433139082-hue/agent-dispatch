# ADR-0009 分层与写权：技能源码单写者，计划与状态归项目

- 状态：Accepted（2026-10-22，甲方提问触发：「是不是不要都放在 agent-dispatch 这个项目里，放到各自的项目下，或者像 ask-matt 一样，各个项目有各个项目的计划」）
- 触发：同日两次撞车 —— 两个会话同时改 `E:\beikong-code\agent-dispatch`（`seats.py` / `packet.py` 与另一份 `lifecycle.py` 同一分钟落盘；`cli.py` 互相覆盖）。

## 1. 三层，各管一件事

| 层 | 放什么 | 谁写 | 现状 |
|---|---|---|---|
| **技能层**（`agent-dispatch` 源码仓 / `~/.agents/skills/agent-dispatch` 安装副本） | 命令实现、模板、契约文档、技能自身的 ADR | **单写者**：只有"技能会话"可改；其它会话只准用 CLI | 撞车就发生在这层 |
| **项目层**（各业务仓，如 `E:\eohm-replica`） | `tickets/`、`.dispatch/`（runs/state/seats）、`docs/specs/`、`docs/selection/`、`docs/adr/`、`CONTEXT.md` | 项目会话（它自己的计划与档案） | 已经是这样，但没写成规则 |
| **会话层**（一次执行） | 一票一 worktree、receipt、verify、closeout | 执行者 | 已隔离 |

结论：**计划、票、规格、选型、验收证据一律留在各自项目里**（已经是事实）；撞车不在"放哪"，而在**技能源码被多个会话同时改**。

## 2. 决策

### D1 技能源码单写者

- 同一时刻只允许一个会话持有技能仓写权；换手要交接。
- 其它会话要改技能：**开票到技能仓的 `tickets/`**，由当前写者执行，不直接改源码。
- 落地：技能仓 `AGENTS.md` 写死这条 + 建议加 `CODEOWNERS` / 分支保护。

### D2 项目层自足

- 每个项目自带 `tickets/`、`.dispatch/`、`docs/specs`、`docs/selection`、`docs/adr`、`CONTEXT.md`。
- **技能只提供能力，不保存项目事实**；升级技能不得迁移项目数据。
- 与 ask-matt 同构：那边每个项目有自己的 plan/tickets（`.scratch/<slug>/issues/`），这边是 `tickets/` + `.dispatch/`。

### D3 版本钉住

- 项目记录所用技能版本；升级走单独动作，不随项目票悄悄发生。

## 3. 后果

- 正面：撞车面从"任意会话"收敛到"一个写者"；项目事实永远跟项目走，换技能不丢。
- 负面：改技能要排队/交接；技能会话成瓶颈（用"技能仓开票 + 定时窗口"缓解）。
