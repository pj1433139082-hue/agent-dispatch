---
name: implement-spec-dispatch
description: 一条线跑完"规格 → 票 → 落地"：读 docs/specs/<slug>.md，出票（缺的补问），逐票 brief/render/verify/review/land，每票一停。触发：implement-spec-dispatch、按规格全部做完、spec 直接落地、整份规格执行。
---

# 规格 → 票 → 落地（一条龙）

规格已定稿时用。上游 **to-spec-dispatch**，本技能把 **to-tickets-dispatch + implement-dispatch** 串起来。

## 前置

- `docs/specs/<slug>.md` 存在且已 `confirm`
- `dispatch setup` 跑过（票目录/执行端已配）

## 干法

```bash
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py stage <slug>              # 先看 S3/S4/S5 到哪一步
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py tickets <slug>            # 没有票就先拆
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py lint && plan              # 校验 + 分波
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py status                    # 拿 frontier
```

然后**逐票**（每票一个新的上下文窗口）：

```bash
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py brief <id> → 填 → --approve <你>
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py render <id> --agent <执行者>
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py start <id> → 执行 → python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py verify <id>
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py review <id> --reviewer <另一人> --verdict pass   # L2+ 带 --packet-hash
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py land <id>
```

全部 done 后：`python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py land --wave`（仍不 push）。

## 两条硬规则

1. **一票一停**——`auto` 是单票推进器；整波连跑会 prompt_too_long。要连跑就每票之间开新会话/压缩上下文。
2. **缺的票不要瞎补**——Delivery standard 不够细，回 **to-spec-dispatch** 补规格，别在票里临时发明需求。

## 出问题

`doctor` → `doctor --fix` → `retry <id>` → `sweep` → `release <id>`