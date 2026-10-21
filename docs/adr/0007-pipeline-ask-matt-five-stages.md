# ADR-0007 编排主流程：需求对齐 → 拷问+选型 → 规格 → 拆票 → 实现

- 状态：**Accepted**（2026-10-22 口述提出；同日问卷回收 Q1/Q3/Q6/Q8/Q11 后定稿）
- 影响范围：agent-dispatch 技能的主流程（不是新增独立框架）、与 ask-matt / grill-with-docs / to-spec / to-tickets / implement-spec 的衔接
- 前置：ADR-0006（上下文包 / 两阶段 brief / 失败回灌 / 收口）

## 1. 用户原话（甲方口径，逐句归并）

> 审批什么的流程的 我希望这套可以用 /to-questionnaire 向我对齐需求就行，给 agent 更多的自动化权限，然后主要是对齐我的功能需求还是交付标准等等，就是把我当成甲方，然后你的技术选型的问题还有一些东西都可以交给 agentteam 或者子 agent 讨论的。主线还是要是我说的那套 ask-matt 的流程跑任务，然后分发：
> ① 向我询问具体的需求 → ② /grill-with-docs，然后对每个问题进行技术选型（可分发子 agent：做开源优秀项目借鉴、搜索引擎获取信息、多角色对抗性审查）→ ③ /to-spec 做颗粒度对齐（主要看交付标准是否合理）→ ④ /to-tickets 分发人格、分发 agent 任务，或者 /implement-spec。

## 2. 五段主流程（本 ADR 的骨架）

| # | 阶段 | 谁做 | 产出 | 甲方参与点 |
|---|---|---|---|---|
| S1 | 需求对齐 | lead 用 `to-questionnaire` 出问卷 | `to-questionnaire-<slug>.md`（甲方填） | **甲方回答**（功能需求 + 交付标准） |
| S2 | 拷问 + 技术选型 | `grill-with-docs` 主拷问；每个问题分发子 agent 并行：开源项目借鉴 / 搜索取证 / 多角色对抗性审查 | ADR（每个决策一份）+ 选型证据表 | 只看结论与冲突项 |
| S3 | 规格与颗粒度对齐 | `to-spec` | spec（Problem / Solution / Stories / Decisions / Testing / Out of scope） | **甲方确认交付标准**（验收是否可命令化） |
| S4 | 拆票与派单 | `to-tickets` + `assign`（人设） | 票据 + 依赖边 + persona | 抽查颗粒度 |
| S5 | 实现 | `implement-spec`（子 agent 并行 worktree）或 `auto` | 每票 receipt + verify + closeout | 收口校验签字 |

## 3. 与已实现能力的关系（v0.8.0）

| 阶段 | 已被本仓覆盖的部分 | 缺口 |
|---|---|---|
| S1 | 无 | 问卷模板与落点、答案回收后如何转成 spec 输入 |
| S2 | `persona`（谁来做）、`export --format agent-team`（多角色并行） | 选型证据的强制门槛（开源参照数、对抗性审查角色、搜索取证留痕） |
| S3 | 无 | 「交付标准」的结构化表达（现在散落在 Acceptance 里） |
| S4 | `lint` / `plan` / `assign` / `new` | 票据从 spec 的自动切分 |
| S5 | `render` / `context` / `brief` / `checkpoint` / `verify` / `review` / `closeout` / `land` | 无 |

## 4. 决策草案（待问卷确认后转 Accepted）

- **D1** 主流程不新增独立框架，串既有技能；agent-dispatch 只负责 S4/S5 的契约与门禁。
- **D2** S1 的问卷即「甲方对齐入口」，取代逐条问答；一次只发一份问卷，问题按影响面排序。
- **D3** S2 的选型必须留证：≥2 个开源参照（含具体文件/函数）、≥1 轮对抗性审查意见、明确「不采用」的理由。
- **D4** S3 的交付标准必须先可命令化（`Verify` 能跑）再进 S4；不可命令化的部分写进 Out of scope。
- **D5** S5 默认走子 agent 并行 worktree + 两阶段 brief；看板仅作可选落库（ADR-0006 D1）。

## 5. 后果

- 正面：甲方只在 S1/S3 两个点上深度参与，其余交给 agent；每段都有文件留痕，会话中断不丢上下文。
- 负面：S1 问卷本身需要甲方花 10–20 分钟；S2 的子 agent 并行会消耗额度。
- 未定：问卷是否复用 `ask_user_question` 交互、还是纯 Markdown 文件（见问卷 Q7）。


## 6. 问卷回收（2026-10-22，甲方答）

| 问 | 结论 |
|---|---|
| Q1 卡点 | **S1 + S2 + S3 三处停**：问卷回答、选型结论、交付标准都要甲方签字；S4/S5 全自动 |
| Q3 交付标准形式 | **可命令化验收命令 + checkbox 清单**（命令是硬门禁，checkbox 供人工核对） |
| Q6 子 agent 授权 | **独立 worktree 写代码，不 push**；推送与合并要甲方点头 |
| Q8 选型证据门槛 | **≥2 个开源参照（指到文件/函数）+ ≥1 轮对抗性审查**，并写明不采用的理由 |
| Q11 固化方式 | **加薄包装命令** `align` / `spec` / `tickets` |

补充需求（甲方原话）：**问卷要分级，让用户自己选择提问的颗粒度**。已落成三档：`quick` 3 问 / `standard` 6 问 / `thorough` 10 问，问卷第一段就是档位选择，改一行即可换档。

## 7. 落地状态（v0.9.0）

| 阶段 | 命令 | 状态 |
|---|---|---|
| S1 | `dispatch align <slug> [--level quick\|standard\|thorough]` | 已实现：出 `docs/questions/<slug>.md`，含档位表与分级问题 |
| S3 | `dispatch spec <slug>` | 已实现：问卷未答满（仍有空 `>` 行）时拒绝写规格；`--force` 可跳过 |
| S4 | `dispatch tickets <slug>` | 已实现：从规格的 `## Delivery standard` 逐条生成草稿票到 `.dispatch/drafts/<slug>/`（`Status: draft`，补 Write scope/Verify 后才进 `tickets/`） |
| S2 | `dispatch select <slug>` | 已实现：出 `docs/selection/<slug>/` 证据包。**三角色必须**（`oss-scout` / `search-scout` / `adversary`，人设随技能分发），可选 `domain-owner` / `cost-keeper`，`--add id:persona` 可挂自定义角色；汇总表留甲方签字行 |
| S5 | `render/context/brief/checkpoint/verify/review/closeout/land` | 已实现（v0.7.1–v0.8.0） |
