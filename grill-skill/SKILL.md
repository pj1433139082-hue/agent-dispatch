---
name: grill-dispatch
description: 我们的拷问阶段：问需求 + 三视角取证（开源借鉴/事实核查/对抗审查），把对抗的假设变成下一轮问题。产出 docs/questions/<slug>.md 与 docs/selection/<slug>/ 证据包。触发：grill-dispatch、拷问需求、需求澄清加取证、技术选型前调研。
---

# 1/4 · Grill（边问边取证）

链条：**grill-dispatch → to-spec-dispatch → to-tickets-dispatch → implement-dispatch**

## 做什么

1. 出问卷：`python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py align <slug> --level standard`（quick 3 / standard 6 / thorough 10）
2. 出角色 brief（**注意：`select` 生成的是 brief，不是证据**；执行者要把 `01/02/03` 原地改写成证据；重跑 `select` 会重写 `99-summary.md`，先备份）：`python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py select <slug> --with domain-owner,cost-keeper`
3. 派三个执行者填三份证据（有 teammate 用 send_message；没有就自己写，文件里标注"主代理代做"）：
   - `01-oss.md`：≥2 个开源参照，指到 `文件:函数` 或 commit，并写**不采用的理由**
   - `02-sources.md`：每条事实带 URL + 原文摘录 + 抓取日期 + 版本
   - `03-adversary.md`：没说出口的假设，每条给可证伪实验（≤7 条）
4. **等 adversary 把 03 写完再问**（还是模板时 `questions` 会拒绝）
5. **把对抗变成问题**：只读 `## 假设` 小节（`## 未证实项` 不会被当成问题；文件里没有"假设"标题时才退化成读全文所有 bullet），最多取 20 条；以"写 "/"证据门槛"/"只读"开头的模板说明和 `<`/`TODO` 占位会被**跳过并在 stderr 说明**：`python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py questions <slug> --json` → 原样喂 `ask_user_question` → 答案写回 `docs/questions/<slug>.md`

## 几个容易踩的细节

- **档位 ≠ 空行数**：`--level standard` 是 6 问，但模板有 **7 个 `> `**（6 问 + 最后的 `Anything else?`）。**全部都要填**，留一个空 `spec` 会拒："还有 1 个问题没填"。
- **可选角色 04/05**：`--with domain-owner,cost-keeper` 只多两个 brief；写最小证据即可，**不写不卡 `sign`**（`sign` 只改签字三行）。
- **`99-summary` 的表格不影响门禁**：`sign` 不校验表格，`spec` 只校验签字行——但填了才好审计。
- **`questions` 的 stderr 只报条数**，不列具体哪几条被跳过；`TODO` 是**包含匹配**（行内任何位置出现都跳过）。

- **单 agent 会话里谁签**：没有人类通道时以**主代理名义**代签（`--by lead --via card`），并在交付说明里注明"代为签字"。
- **`sign` 会自动写日期**；`99-summary` 的 `- 日期：` 不用手填。

## 收敛标准

- 问卷答满（对应档位）
- `03-adversary.md` 没有新假设
- `01-oss.md` 每条参照都有"不采用理由"

## 交给下一步

- 签字：`python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py sign <slug> --by <你> --via card`（写进 `99-summary.md`）
- 然后进 **to-spec-dispatch**

收工/换会话前：`dispatch wrap`（有问题 exit 1）

## 别硬走

- 想法还没成形 → `grill-me`
- 只查资料不落地 → `research` / `exa-search`