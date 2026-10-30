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
2. 出角色 brief（**注意：`select` 生成的是 brief，不是证据**；执行者要把 `01/02/03` 原地改写成证据；重跑 `select` 会重写 `99-summary.md`，先备份）：`python ...\dispatch.py select <slug> --mode team`（写域受限时省略 `--with`；有 teammate 工具时默认 `team`，见下节）
3. 派三个执行者填三份证据（有 teammate 用 send_message；没有就自己写，文件里标注"主代理代做"）：
   - `01-oss.md`：≥2 个开源参照，指到 `文件:函数` 或 commit，并写**不采用的理由**
   - `02-sources.md`：每条事实带 URL + 原文摘录 + 抓取日期 + 版本
   - `03-adversary.md`：没说出口的假设，每条给可证伪实验（≤7 条）
4. **等 adversary 把 03 写完再问**（还是模板时 `questions` 会拒绝）
5. **把对抗变成问题**（`questions` 只给"成立/不成立/不确定"三个选项，**不生成推荐**——喂给用户前你要先替每题选一个推荐并在正文里写明理由）：只读 `## 假设` 小节（`## 未证实项` 不会被当成问题；文件里没有"假设"标题时才退化成读全文所有 bullet），最多取 20 条；以"写 "/"证据门槛"/"只读"开头的模板说明和 `<`/`TODO` 占位会被**跳过并在 stderr 说明**：`python ...\dispatch.py questions <slug> --json` → 喂 `ask_user_question`（选项照传，推荐写在你自己的话里）→ 答案写回 `docs/questions/<slug>.md`

## 三会话并行（team 模式，v1.9.0）

`select --mode team` 把证据包标记成"每份证据由独立子会话产出"。之后：

1. **spawn 三个 fresh teammate**（`spawn_teammate({name, description, prompt})`），一个角色一个，不共享上下文：
   - `name`：`grill-oss` / `grill-search` / `grill-adversary`
   - `prompt` = ①该角色 persona 正文（`agents/personas/<id>.md` 全文）②自己的 brief（mission + 证据门槛 + **只许写自己的文件**）③下面的信息源隔离表 ④回收格式
2. **信息源隔离**（否则三个都会去搜同一批东西）：

   | 角色 | 只准 | 禁止 |
   |---|---|---|
   | oss-scout | 代码仓、包管理器、源码、commit | 博客/二手文章；把官方文档结论当证据 |
   | search-scout | 官方文档、changelog、issue、release notes | 读源码代替文档；凭记忆给版本 |
   | adversary | 读方案 + 另两份证据（交叉质疑） | 自己再做检索（那就变回搜索员） |

3. **回收格式**（每个 teammate 结束时只回这五行）：
   ```
   文件：docs/selection/<slug>/01-oss.md
   结论：建议采用 X（或 建议不采用 / 证据不足）
   依据：<3 行以内，指到 文件:函数 / URL+日期+版本>
   置信度：高 / 中 / 低 + 一句为什么
   未证实：<逐条，没有写"无">
   ```
4. **等齐再往下**：`wait_agent` 到三个都结束；任何一个超时/失败，就把它那份标 `未产出` 并在 99-summary 写明，不许主代理悄悄补写成"已完成"。
5. **交叉评审（必做一轮）**：三份齐了之后，让每个 teammate **只读另外两份**，回一条反驳：
   ```
   质疑对象：02-sources.md 的 <结论>
   反驳：<一句话 + 依据>
   要求补的证据：<最小实验 / 具体来源>
   ```
   Lead 把三条反驳写进 `docs/selection/<slug>/06-cross-review.md`，分歧结论回填 `99-summary.md` 的"决策"段。
6. **签字门会验**：`sign` 在 team 模式下要求每份证据①存在 ②带 `Persona: <角色 persona>` 行 ③不再是 `## What to produce` 模板；缺一条就拒绝签字。

**没有 teammate 工具 / spawn 失败时**：退回 `--mode solo`，三份证据由主代理代做，每份文件头写 `Persona: <角色 persona>（主代理代做）`，并在 99-summary 标注 `模式：solo`。降级可以，但必须留痕。

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
- team 模式：三份证据都带 `Persona:` 行、`06-cross-review.md` 存在且三条反驳齐全；solo 模式：三份都标了"主代理代做"

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
