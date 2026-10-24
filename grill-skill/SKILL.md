---
name: grill-dispatch
description: 我们的拷问阶段：问需求 + 三视角取证（开源借鉴/事实核查/对抗审查），把对抗的假设变成下一轮问题。产出 docs/questions/<slug>.md 与 docs/selection/<slug>/ 证据包。触发：grill-dispatch、拷问需求、需求澄清加取证、技术选型前调研。
---

# 1/4 · Grill（边问边取证）

链条：**grill-dispatch → to-spec-dispatch → to-tickets-dispatch → implement-dispatch**

## 做什么

1. 出问卷：`python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py align <slug> --level standard`（quick 3 / standard 6 / thorough 10）
2. 出证据包：`python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py select <slug> --with domain-owner,cost-keeper`
3. 派三个执行者填三份证据（有 teammate 用 send_message；没有就自己写，文件里标注"主代理代做"）：
   - `01-oss.md`：≥2 个开源参照，指到 `文件:函数` 或 commit，并写**不采用的理由**
   - `02-sources.md`：每条事实带 URL + 原文摘录 + 抓取日期 + 版本
   - `03-adversary.md`：没说出口的假设，每条给可证伪实验（≤7 条）
4. **把对抗变成问题**：`python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py questions <slug> --json` → 原样喂 `ask_user_question` → 答案写回 `docs/questions/<slug>.md`

## 收敛标准

- 问卷答满（对应档位）
- `03-adversary.md` 没有新假设
- `01-oss.md` 每条参照都有"不采用理由"

## 交给下一步

- 签字：`python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py sign <slug> --by <你> --via card`（写进 `99-summary.md`）
- 然后进 **to-spec-dispatch**

## 别硬走

- 想法还没成形 → `grill-me`
- 只查资料不落地 → `research` / `exa-search`