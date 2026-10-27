---
name: to-spec-dispatch
description: 把已拷问过的需求收敛成规格：写 docs/specs/<slug>.md（Problem/Solution/Stories/Delivery standard/Decisions/Testing/Out of scope），三角色逐段挑刺，最后 confirm 签字。触发：to-spec-dispatch、出规格、写 spec、规格确认。
---

# 2/4 · Spec

上一步：**grill-dispatch**　下一步：**to-tickets-dispatch**

## 前置

- `docs/questions/<slug>.md` 答满
- `docs/selection/<slug>/99-summary.md` 已签字（`sign --by <你> --via card`）

## 做什么

```bash
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py spec <slug>        # 问卷没答满 / S2 没签字 → 拒绝；--force 跳过（不推荐）
```

产出 `docs/specs/<slug>.md`：Problem / Solution / Stories / Delivery standard / Implementation Decisions / Testing / Out of scope。

**三角色逐段挑刺**（各写一段评论，结论写进 `## Implementation Decisions`（`spec` 模板的正式小节名，口头叫 Decisions 也是它））：

| 角色 | 挑什么 |
|---|---|
| oss | 有没有现成方案被忽略 |
| search | 有没有事实/版本写错 |
| adversary | 哪条"决策"其实是没验证的假设 |

## 门

```bash
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py confirm <slug> --by <你> --via card
```

没 confirm 过，`tickets` 拒绝拆票。

## Delivery standard 怎么写

每行一条 `- [ ] …`，**一条 = 一个可独立验收的切片**——后面拆票就按它拆。