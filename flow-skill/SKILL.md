---
name: dispatch-flow
description: 派单流程路由：判断手上的活该走「需求→票」「单票执行」「批量自动」「运维恢复」哪条流程，每一步该调哪个 skill、哪条 dispatch 命令，以及交给谁执行。触发：怎么派单、走哪条流程、dispatch 流程、这张票怎么推、票卡住了怎么办。
---

# Dispatch Flow（自有流程路由，不改 ask-matt）

> 这是**我们自己的**流程路由，与 @ask-matt@ 无关；ask-matt 是 Matt 的技能，不动它。
> 机制细节在 `agent-dispatch` 的 `docs/flows.md`；本卡只做"选路 + 每步调谁"。

## 接在你现有流程上（重要）

平时的 `grill-with-docs → to-spec → to-tickets → implement` **不用换**；dispatch 替掉的是 **to-tickets 之后的 implement**：

| 你手上有什么 | 前面照旧 | dispatch 从哪接 |
|---|---|---|
| 想法 | grill-with-docs → to-spec | 出票后从 B 开始 |
| spec | to-spec | `dispatch tickets <slug>` → lint |
| 票 | to-tickets | **直接 B**：brief → render → 执行端 → verify → review → land |
| 什么都没有 | 可跳过 | align → select → sign → spec → confirm → tickets（可选入口） |

只打了 `/agent-dispatch` 时：**先问"票在哪"**，再 `dispatch lint` → `dispatch status` → 挑 frontier 走 B。

## 先问三句

1. **有没有票？** 没有 → 流程 A；有 → 流程 B。
2. **一张还是整波？** 一张 → B；整波/半自动 → C。
3. **是不是坏了/卡住了？** 是 → D；不是 → 继续。

## 流程 A｜需求 → 票（S1–S5）

| 步 | 调什么 | 命令 |
|---|---|---|
| A1 想清楚 | `grill-with-docs` / `grilling`（产出 ADR、术语） | — |
| A2 出规格 | `to-spec` 或 dispatch 内置 `spec` | `dispatch align <slug>` → `dispatch spec <slug>` |
| A3 选型取证 | `agent-dispatch` 的三角色（oss-scout / search-scout / adversary） | `dispatch select <slug>` → 人签字 `dispatch sign` |
| A4 确认交付 | 人核对 | `dispatch confirm <slug> --by … --via …` |
| A5 拆票 | `to-tickets` 或 dispatch | `dispatch tickets <slug>` → 补写域/验证 → `dispatch lint` |

## 流程 B｜单票执行

| 步 | 调什么 | 命令 |
|---|---|---|
| B1 校验分波 | — | `dispatch lint` → `dispatch plan` |
| B2 先想后做 | `grill-me`（小）/ `codebase-design`（接口拿不准） | `dispatch brief <id>` → 人批 `dispatch brief <id> --approve <人>` |
| B3 开工作单 | — | `dispatch render <id> --agent <名字>` |
| B4 派人 | 见"执行端" | `dispatch handoff <id> --to <agent>` |
| B5 实现 | `implement` / `implement-spec`，内部用 `tdd` | 执行端在 worktree 干 |
| B6 验收 | `verification` 的态度 | `dispatch verify <id>` |
| B7 评审 | `code-review` 当 reviewer | `dispatch review <id> --reviewer <非执行者>` |
| B8 落地 | — | `dispatch land <id>` |
| B9 出 PR | `pr` 写正文 | 人开 PR |

## 流程 C｜批量与自动

- 单票半自动：`dispatch auto <id> --executor "<cmd>" [--until review|land]`
- 整波落地：`dispatch land --wave`（拓扑序）
- 纪律：**auto 一票一停**，别把整波塞进一个上下文。

## 流程 D｜运维恢复

| 症状 | 命令 |
|---|---|
| 不知道哪不对 | `dispatch doctor` |
| 索引/磁盘不一致 | `dispatch doctor --fix` |
| 票 failed | `dispatch retry <id> --reason …` |
| 文件被占 | `dispatch release <id>`（对方） |
| run 超期/僵尸 | `dispatch sweep` → `dispatch repair --write` → `dispatch gc --apply` |

## 执行端选谁（dispatch 不创建 agent）

| 会话里有什么 | 用哪条 |
|---|---|
| `list_agents` 有目标 teammate | B4 `handoff --to <它>` + `send_message` |
| DSH 看板在跑 | `dispatch dsh push` 建卡 → 板上点 run / `dsh run` → `dsh outcome` 回写 |
| 都没有 | `auto --executor "<cmd>"`，**并说明这是主代理自执行** |

## 与其它技能的边界

- `ask-matt`：Matt 的总路由，**不改它**；本卡只覆盖派单这一段。
- `to-tickets` / `to-spec`：可以替代 A2/A5，产物放进 `tickets/` 即可。
- `handoff`（会话交接）：与本卡 B4 的"工作单交接"不是一回事，前者交上下文，后者交执行。
