---
name: to-tickets-dispatch
description: 把规格拆成可执行票据：一条 Delivery standard 一张票，带 What/Blocked by/Owner/Risk/Write scope/Verify/Acceptance，跑 lint 与 plan，按依赖分波。触发：to-tickets-dispatch、拆票、任务拆分、写域划分、依赖分波。
---

# 3/4 · Tickets

上一步：**to-spec-dispatch**　下一步：**implement-dispatch**

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

## 写域冲突怎么办

`plan` 报 `Conflict A / B: path` 时：**不阻止单票执行，但这两张不能同波并行**。三选一——改其中一张的写域、串行做、或者把它们并成一张票。历史遗留票的冲突不用为了跑新票去改它。

## Status 的例外

`land --wave` 会读**票面**的 `Status: done` 来决定跳过哪些票；单票 `land <id>` 看的是 `state.json`。所以票面 Status 平时只是备注，走整波时它会生效。

## stage 的 s4 数字

`stage` 里 `s4: N draft(s)` 统计的是 `.dispatch/drafts/<slug>/` 里**还剩几个文件**，不是"还有几张票没补"。挪完票再删掉草稿，这个数字就归零（删不删都不影响 lint/tickets）。

## 拆票规则

- 一张票 = 一个可独立验收的切片
- **写域不重叠的票才能同波并行**
- 有依赖就写 `Blocked by`，别靠嘴说顺序
- 要人设：`personas list` → `assign <id> --persona <短名>`