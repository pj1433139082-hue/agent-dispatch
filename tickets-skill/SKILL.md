---
name: to-tickets-dispatch
description: 把规格拆成可执行票据：一条 Delivery standard 一张票，带 What/Blocked by/Owner/Risk/Write scope/Verify/Acceptance，跑 lint 与 plan，按依赖分波。触发：to-tickets-dispatch、拆票、任务拆分、写域划分、依赖分波。
---

# 3/4 · Tickets

上一步：**to-spec-dispatch**　下一步：**implement-dispatch**

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

## 拆票规则

- 一张票 = 一个可独立验收的切片
- **写域不重叠的票才能同波并行**
- 有依赖就写 `Blocked by`，别靠嘴说顺序
- 要人设：`personas list` → `assign <id> --persona <短名>`