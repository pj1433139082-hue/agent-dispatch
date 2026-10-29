---
name: to-tickets-dispatch
description: 把规格拆成可执行票据：底座是 to-tickets（tracer-bullet 垂直切片、预重构、宽改 expand–contract、拆完要人审、按依赖顺序发布），dispatch 层加票面契约（Owner/Risk/Write scope/Verify/Persona）、lint 与 plan 分波。触发：to-tickets-dispatch、拆票、任务拆分、写域划分、依赖分波。
---

# 3/4 · Tickets

上一步：**to-spec-dispatch**　下一步：**implement-dispatch**

## 底座：先加载原技能

`Skill("to-tickets")` —— **怎么切**以它为准：

- **先拿全上下文**：读 `docs/specs/<slug>.md` 全文（有评论/批注也要读）。
- **可以先把路修平**（prefactor）：如果某个改动会让后面每张票都难写，先开一张预重构票把它做掉——"先让改动变容易，再做容易的改动"。
- **每张票是 tracer bullet 垂直切片**：切一条窄但**完整**的路径（schema → 接口 → UI → 测试都碰得到），不是某一层的横切；**单独就能演示或验收**；**装得进一个全新上下文窗口**。
- **宽改例外**：一次机械改动（改列名、改共享类型）的爆炸半径横跨整个仓库时，别硬切成垂直切片，改成 **expand–contract**：先加新形态（旧的还在，谁都不坏）→ 按爆炸半径分批迁移（每批一张票，都 blocked by expand）→ 没人用旧形态后再删旧形态（blocked by 所有迁移票）。各批单独跑不绿时，让它们共用一条 integration branch，最后再挂一张 integrate-and-verify 票。
- **每张票写清 blocking edges**：没有依赖的票＝可以马上开工。
- **拆完先给人看**：逐张给 Title / Blocked by / What it delivers（这一票做完什么端到端行为），然后问三件事：粒度对不对？依赖边是否只保留了真正的门？有没有该合并或再拆的？改到用户点头再落盘。
- **按依赖顺序发布**（被依赖的在前），一次一票、不要合成一个大文件。
- "What to build" 写**用户视角的端到端行为**，不是逐层实现清单；正文别写具体文件路径和代码片段（会过期），原型里的决策片段除外。

本文件只写 **dispatch 差异层**：票面多 Owner/Risk/Write scope/Verify/Persona 四类字段、产物落 `tickets/`、`lint`/`plan` 门。冲突裁定：**怎么切听 to-tickets，票面字段与目录听本文件**。原技能装不上就明说，不要凭记忆补它的步骤。

## 建票时顺手绑人格（v0.95）

```bash
dispatch new 01 --title "runtime 侦察" --owner recon-runtime \
  --what "读运行时并写报告" --write-scope reports/01.md \
  --persona dispatcher.md
```

- `--persona` 收 `tickets/personas/` 下的文件名（或 `--search-root` 找得到的名字）。
- 它会：复制人格文件 → 写 `- Persona:` 行 → 追加 `.dispatch/assignments.jsonl`。
- 不写也不会报错，但 **L2+ 的票在 `render` 时会被人格门挡住（exit 6）**，所以高风险票请一开始就写。
- L0/L1 可以留空（`(unassigned)`）；抢时间的小改别为了走流程硬造人格。

## 票面可选字段

- `Requires: local | network | ssh | browser`（默认 `local`）：声明执行端需要什么；现在只做 lint 警告。

## Verify 怎么写（硬要求）

- **本机可跑**：不依赖 ssh / 远端 / 浏览器 / 登录态。
- **幂等**：连跑两次结果一样。
- **无网络、< 5 分钟**。
- 需要远端事实 → 先落快照（带时间戳），Verify 只断言快照。

## 两条路

**A 自动拆**（spec 里有 `## Delivery standard`）：

```bash
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py tickets <slug>          # 草稿写到 .dispatch/drafts/<slug>/
# 补齐每张票的 Write scope / Verify，挪进 tickets/
```

**B 手写**（spec 是 to-spec 那套格式、没有 Delivery standard）：一条一条写 `tickets/NN-slug.md`：

```markdown
# 01: <标题>

## What to build

一句话说清"做完后什么能用"。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: src/xxx.py
- Verify: python -m pytest -q tests/test_xxx.py

## Acceptance

- [ ] 具体可验收的一条
```

拆出来的票 **id 由标题 `# <id>:` 决定**（不是文件名），文件名 `01-<slug>.md`，后面 `brief 01` 用这个号。

**合并进已有 `tickets/` 前**：先分配一个没被占用的号（改成 `# 05: …` + `05-<slug>.md`），把 `（待填）` 填掉——否则 `lint` 报 `placeholder_value`；票号没换则报 `duplicate_id`。

`Status:` 只是**给人看的建议值**（契约里可选，工具不校验它），改成 `ready-for-agent` 只为可读性，lint 不看它。

## 校验

```bash
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py lint      # 缺字段/环/未知依赖/占位值都会拒
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py plan      # 拓扑波次 + 同波写域冲突
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py status    # frontier 是哪几张
```

## 占位 checkbox 不用管

`spec` 模板自带的 `- [ ] （可命令化的验收项）` / `- [ ] （人工核对项）` 会被 `delivery_items` **忽略**（以 `（` 开头即跳过），删不删都行；补一条真项即可。

## 工具副作用（写域之外）

- `tickets <slug>` 一定把草稿写到 `.dispatch/drafts/<slug>/`；这是「两条路 A」的正常产物，但它在**写域之外**。挪完票把草稿删空，`stage` 的 `s4` 才会归零。
- `select` 的 `00-panel.json`、`--with` 多出的 04/05 也在写域之外，见 grill-dispatch 的「容易踩的细节」。

## 写域冲突怎么办

`plan` 报 `Conflict A / B: path` 时：**不阻止单票执行，但这两张不能同波并行**。三选一——改其中一张的写域、串行做、或者把它们并成一张票。历史遗留票的冲突不用为了跑新票去改它。**新票撞历史票**（例：历史票 24 占着 `tools/`，新票 46 也要写 `tools/`）时不要改历史票：把新票排在它之后（写进 `Blocked by`，或按 `plan` 的冲突提示串行），或者给新票换一个不重叠的写域。

## Status 的例外

`land --wave` 会读**票面**的 `Status: done` 来决定跳过哪些票；单票 `land <id>` 看的是 `state.json`。所以票面 Status 平时只是备注，走整波时它会生效。

## stage 的 s4 数字

`stage` 里 `s4: N draft(s)` 统计的是 `.dispatch/drafts/<slug>/` 里**还剩几个文件**，不是"还有几张票没补"。挪完票再删掉草稿，这个数字就归零（删不删都不影响 lint/tickets）。

## 与 to-tickets 的冲突裁定

| to-tickets 的做法 | 本流程替换为 |
|---|---|
| 发布到 `.scratch/<slug>/issues/` 或真实 tracker | `tickets/NN-slug.md`（先 `dispatch tickets` 出草稿再挪）；不建 tracker issue |
| 票面只有 What/Blocked by/Status/Acceptance | 多了 `## Dispatch` 段：Owner / Risk / Write scope / Verify / Persona |
| 正文不写文件路径 | 正文照旧不写；但 `Write scope` 是**契约字段**，必须写路径——这是裁判要用的，不是说明文字 |
| 不关不改父 issue | 没有父 issue 概念；合并进已有 `tickets/` 时只加新票，不改别人 |

## 上游锚点

- 底座：mattpocock/skills 的 `skills/engineering/to-tickets`。
- 原技能更新后，复核三处：①垂直切片四条规则 ②宽改 expand–contract 序列 ③"拆完先给人看"的三问。
