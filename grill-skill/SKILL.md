---
name: grill-dispatch
description: 我们的拷问阶段：底座是 grilling（设计树 + 分轮问前沿 + 每题给推荐答案），上面加 dispatch 的三视角取证（开源借鉴/事实核查/对抗审查）与问卷、签字留痕。产出 docs/questions/<slug>.md 与 docs/selection/<slug>/ 证据包。触发：grill-dispatch、拷问需求、需求澄清加取证、技术选型前调研。
---

# 1/4 · Grill（边问边取证）

链条：**grill-dispatch → to-spec-dispatch → to-tickets-dispatch → implement-dispatch**

## 底座：先加载原技能

1. `Skill("grilling")` —— **怎么问**以它为准：
   - 把方案当**设计树**：每个决策分出挂在它下面的决策；**前沿（frontier）**＝前提已经定了的问题，只能问当前前沿。
   - **一轮问一个前沿**：逐条编号提问，每题都给**你推荐的答案**（`❓ Q1 … ➡️ …`），措辞要让"是"＝接受推荐。
   - 答案会改变的问题留到**下一轮**；每轮拿到回答后重算前沿，再问下一轮。
   - **事实自己查**（派子智能体读仓库/查版本/查文档），只把**决策**交给用户；查事实不许阻塞其他问题的追问。
   - 前沿为空 + 用户确认"共识达成"才算收敛；没确认不许往下走。
2. 涉及架构决策或领域术语时再 `Skill("domain-modeling")`：ADR 落 `docs/adr/`（接现有编号），术语进 `GLOSSARY.md`。
3. 本文件只写 **dispatch 差异层**：产物放哪、留哪三份证据、什么算签字。冲突裁定：**问法听 grilling，产物与门禁听本文件**。原技能装不上就明说，不要凭记忆补它的步骤。

## 做什么

1. 出问卷（**最低集 + 留痕文件**）：`python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py align <slug> --level standard`（quick 3 / standard 6 / thorough 10）
   - 问卷是**起点不是全部**：前沿里问卷没覆盖的问题，按下面「追加轮次」继续问，并写回同一个文件。
2. 出角色 brief（**注意：`select` 生成的是 brief，不是证据**；执行者要把 `01/02/03` 原地改写成证据；重跑 `select` 会重写 `99-summary.md`，先备份）：`python ...\dispatch.py select <slug> --with domain-owner,cost-keeper`
3. 派三个执行者填三份证据（有 teammate 用 send_message；没有就自己写，文件里标注"主代理代做"）：
   - `01-oss.md`：≥2 个开源参照，指到 `文件:函数` 或 commit，并写**不采用的理由**
   - `02-sources.md`：每条事实带 URL + 原文摘录 + 抓取日期 + 版本
   - `03-adversary.md`：没说出口的假设，每条给可证伪实验（≤7 条）
4. **等 adversary 把 03 写完再问**（还是模板时 `questions` 会拒绝）
5. **把对抗变成问题**（`questions` 只给"成立/不成立/不确定"三个选项，**不生成推荐**——喂给用户前你要先替每题选一个推荐并在正文里写明理由）：只读 `## 假设` 小节（`## 未证实项` 不会被当成问题；文件里没有"假设"标题时才退化成读全文所有 bullet），最多取 20 条；以"写 "/"证据门槛"/"只读"开头的模板说明和 `<`/`TODO` 占位会被**跳过并在 stderr 说明**：`python ...\dispatch.py questions <slug> --json` → 喂 `ask_user_question`（选项照传，推荐写在你自己的话里）→ 答案写回 `docs/questions/<slug>.md`

## 追加轮次（grilling 的轮次怎么落盘）

- 每轮**只写当前前沿**：格式 `### Q<n> - <标题>` + `➡️ 推荐答案：…` + `> 用户答案：…`。
- 追加到 `docs/questions/<slug>.md` 末尾新建的 `## 追加轮次（grilling）` 小节；`dispatch questions` 读的是固定题库，追加内容不改变它的判定。
- 用户答"是"就按推荐答案记录；答别的照原话记，别替他改写。
- 事实类问题（版本、API、仓库现状）先派子智能体查清，再把**决策**问给用户。

## 几个容易踩的细节

- **档位 ≠ 空行数**：`--level standard` 是 6 问，但模板有 **7 个 `> `**（6 问 + 最后的 `Anything else?`）。**全部都要填**，留一个空 `spec` 会拒："还有 1 个问题没填"。
- **可选角色 04/05**：`--with domain-owner,cost-keeper` 只多两个 brief；写最小证据即可，**不写不卡 `sign`**（`sign` 只改签字四行）。
- **`99-summary` 的表格不影响门禁**：`sign` 不校验表格，`spec` 只校验签字行——但填了才好审计。
- **`questions` 的 stderr 只报条数**，不列具体哪几条被跳过；`TODO` 是**包含匹配**（行内任何位置出现都跳过）。
- **单 agent 会话里谁签**：没有人类通道时以**主代理名义**代签（`--by lead --via card`），并在交付说明里注明"代为签字"。
- **`sign` 实际改 4 行**：签字人 / 日期 / 选择 / 确认方式（带 `--note` 再多一行 备注）——不是三行。`99-summary` 的 `- 日期：` 仍然不用手填。
- **`select` 必写 `00-panel.json`**（角色面板索引）；`--with domain-owner,cost-keeper` 还会多写 `04-*.md` / `05-*.md` 两个 brief。写域被限死时：去掉 `--with`（不写不卡 `sign`），或先确认这两个文件算不算允许。
- **`questions` 拒绝时退出码是 2**（不是 1），模板检测是字符串匹配：`03-adversary.md` 里出现 `## What to produce` 或 `Persona: builtin:adversary` 就永远判「还是模板」——改写时要把这两处删掉。
- **无人值守（没人能答）**：把问题写进 `docs/questions/<slug>.md` 的 `## 追加轮次（grilling）`，每题带 `➡️ 推荐答案`，答案记 `> 用户答案：是（采纳推荐）`，并在交付说明里写明「无人值守自答」——不要因为没人答就跳过前沿。

## 收敛标准

- 问卷答满（对应档位）
- grilling 的前沿为空，没有悬着没问的决策
- `03-adversary.md` 没有新假设
- `01-oss.md` 每条参照都有"不采用理由"

## 交给下一步

- 签字：`python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py sign <slug> --by <你> --via card`（写进 `99-summary.md`）
- 然后进 **to-spec-dispatch**

收工/换会话前：`dispatch wrap`（有问题 exit 1）

## 别硬走

- 想法还没成形 → `grill-me`（只拷问不留证时用它，别套 dispatch 的问卷/签字）
- 只查资料不落地 → `research` / `exa-search`

## 上游锚点

- 底座：mattpocock/skills 的 `skills/productivity/grilling`（`grill-me` 只是它的别名，`grill-with-docs`＝grilling + domain-modeling）。
- 原技能更新后，只需复核三处差异是否仍成立：①问卷/证据文件路径 ②`questions` 的假设提取规则 ③`sign` 签字门。
