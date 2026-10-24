---
name: grill-dispatch
description: 我们的全流程技能：拷问需求 + 三视角检索/对抗 → 写 spec → 拆票 → 派单并行 → 验收落地。替掉 grill-with-docs→to-spec→to-tickets→implement 这条线，底层用 agent-dispatch。触发：grill-dispatch、拷问并派单、需求到落地、技术选型加拆票、调研后开工。
---

# Grill → Spec → Tickets → Dispatch

一条线跑完，每段都有产物和门。底层命令都在 `agent-dispatch` 里（本技能不重复实现）。

## 什么时候用它

- 你有一个**要做成功能**的想法，想从"问清楚"一路走到"合进分支"。
- 只要其中一段（比如只想拆票）→ 用 `agent-dispatch` 的对应命令，不用整套。

## 四个阶段

| 阶段 | 干什么 | 产物 | 门 |
|---|---|---|---|
| 1 grill | 问需求 + 三视角取证 + 对抗 | `docs/questions/<slug>.md`、`docs/selection/<slug>/01-oss.md / 02-sources.md / 03-adversary.md` | 甲方答完问卷 |
| 2 spec | 收敛成规格 + 逐段挑刺 | `docs/specs/<slug>.md`（含 `## Decisions`） | `confirm --by … --via card` |
| 3 tickets | 拆成可验收小票 | `tickets/NN-*.md` | `lint` / `plan` 通过 |
| 4 dispatch | 逐票执行、验收、评审、落地 | run 目录 + `verify.json` / `review.json` / `landing.json` | verify passed + review pass |

## 1. Grill（边问边取证）

`@bash
D="python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py"
python $D align <slug> --level standard      # 问卷（quick 3 问 / standard 6 / thorough 10）
python $D select <slug> --with domain-owner,cost-keeper   # 三角色必选，另两个可选
`@

然后给三个角色各派一个执行者（有 teammate 就 `send_message`；没有就自己写，**在文件里标注"主代理代做"**）：

- `01-oss.md`：≥2 个开源参照，指到 `文件:函数` 或 commit，**并写不采用的理由**
- `02-sources.md`：每条事实带 URL + 原文摘录 + 抓取日期 + 版本
- `03-adversary.md`：方案没说出口的假设，每条给可证伪实验（≤7 条）

**把对抗变成问题**（这是本技能的关键一步）：

`@bash
python $D questions <slug> --json     # 读 03-adversary.md，输出可直接喂 ask_user_question 的问题
`@

拿到的 JSON 原样问甲方 → 答案写回 `docs/questions/<slug>.md` → 有新假设就再跑一轮。**收敛标准：没有新假设、oss 参照都写了不采用理由。**

## 2. Spec

`@bash
python $D spec <slug>            # 要求问卷答满 + S2 已签字（sign --by … --via card）
`@

写完让三个角色**逐段挑刺**（同一份 spec，各写一段评论）：
- oss：有没有现成方案被忽略
- search：有没有事实/版本写错
- adversary：哪条"决策"其实是没验证的假设

分歧写进 spec 的 `## Decisions`，然后：

`@bash
python $D confirm <slug> --by <你> --via card
`@

## 3. Tickets

`@bash
python $D tickets <slug>         # 按 ## Delivery standard 拆草稿到 .dispatch/drafts/<slug>/
# 补 Write scope / Verify，挪进 tickets/，再：
python $D lint && python $D plan
`@

一张票 = 一个可独立验收的切片；写域不重叠的才能同波并行。

## 4. Dispatch（逐票推进）

`@bash
python $D brief <id>                     # 填五段 → --approve <人>
python $D render <id> --agent <执行者>     # 一票一 worktree
python $D start <id>
# 执行端：teammate（handoff + send_message）/ 看板（dsh push --workspace …）/ 自己干
python $D verify <id>
python $D review <id> --reviewer <另一人> --verdict pass   # L2+ 还要 --packet-hash
python $D land <id>                      # 或 land --wave
`@

规则：**一票一停**，别把整波塞进一个上下文；失败的票 `retry`，不要手改 `state.json`。

## 与 Matt 那套的关系

| 你的旧流程 | 本技能对应 |
|---|---|
| `grill-with-docs` | 阶段 1（多了 oss/search/adversary 取证 + 对抗问题） |
| `to-spec` | 阶段 2（多了三角色挑刺 + confirm 签字） |
| `to-tickets` | 阶段 3（票带写域、Verify、依赖） |
| `implement` | 阶段 4（worktree 隔离 + verify + 异体评审 + landing） |

可以只用其中一段；也可以整套替换。**不改 Matt 的技能。**

## 退出条件（别硬走）

- 想法还没成形 → 先 `grill-me`，别进阶段 2
- 只是单个 bug → `diagnosing-bugs`
- 只有一句话、没有验收标准 → 回到阶段 1 继续问
