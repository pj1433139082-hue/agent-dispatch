---
name: to-spec-dispatch
description: 把已拷问过的需求收敛成规格：底座是 to-spec（不采访只综合、先定测试接缝并与人确认、故事要长、决策与测试小节有写法约束），dispatch 层只加 docs/specs/<slug>.md 模板、Delivery standard、三角色挑刺与 confirm 签字。触发：to-spec-dispatch、出规格、写 spec、规格确认。
---

# 2/4 · Spec

上一步：**grill-dispatch**　下一步：**to-tickets-dispatch**

## 底座：先加载原技能

`Skill("to-spec")` —— 规格的**内容标准**以它为准：

- **不采访**，只综合已经谈过的内容（要问的都在 grill 阶段问完了）。
- 先读仓库现状；用领域术语，尊重相关 ADR。
- **先画测试接缝**：优先用已有接缝，取最高的一条，越少越好（理想是 1 条），并**跟用户确认接缝是否符合预期**。
- **User Stories 要长**：编号列表，覆盖这个功能的各个方面，不是三条示例。
- **Implementation Decisions** 写：要建/改哪些模块、改了哪些接口、技术澄清、架构决策、表结构、API 契约、具体交互。**不写具体文件路径、不贴代码片段**（会很快过期）；例外：原型里能更精确表达决策的片段（状态机/ reducer / schema / 类型）可以内联，并注明来自原型、只留决策相关部分。
- **Testing Decisions** 写：什么算好测试（只测外部行为，不测实现细节）、测哪些模块、仓库里可参考的先例。
- **Out of Scope** 写清这次明确不做什么；**Further Notes** 放其它备注。

本文件只写 **dispatch 差异层**：文件放哪、模板多一节 Delivery standard、三角色挑刺、confirm 门。冲突裁定：**规格内容标准听 to-spec，产物路径与门禁听本文件**。原技能装不上就明说，不要凭记忆补它的步骤。

## 前置

- `docs/questions/<slug>.md` 答满
- `docs/selection/<slug>/99-summary.md` 已签字（`sign --by <你> --via card`）

## 做什么

1. 按 to-spec 第 1–2 步读仓库、列**测试接缝**，把接缝清单发给用户确认（`ask` 槽：DSH=`ask_user_question`，千问办公=`question`）。这一步没有工具门，**必须真问**；不问就直接写规格是漏的。
2. 生成骨架：`python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py spec <slug>`（问卷没答满 / S2 没签字 → 拒绝；`--force` 跳过，不推荐）
3. 按 to-spec 的写法把七节写完：Problem Statement / Solution / User Stories / **Delivery standard** / Implementation Decisions / Testing Decisions / Out of Scope。`Further Notes` 可留空，**不进 S3 门**。
4. **三角色逐段挑刺**（各写一段评论，结论写进 `## Implementation Decisions`——`spec` 模板的正式小节名，口头叫 Decisions 也是它）：

| 角色 | 挑什么 |
|---|---|
| oss | 有没有现成方案被忽略 |
| search | 有没有事实/版本写错 |
| adversary | 哪条"决策"其实是没验证的假设 |

## Delivery standard 怎么写（dispatch 独有）

每行一条 `- [ ] …`，**一条 = 一个可独立验收的切片**——后面拆票就按它拆。占位行（以 `（` 开头）不算数，S3 门会判"只有占位 checkbox"。

## 门

```bash
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py confirm <slug> --by <你> --via card
```

`confirm` 会检查七节非空、非占位；没 confirm 过，`tickets` 拒绝拆票。确认后再改规格正文 → `spec_sha256` 变，需要重新确认。
- **退出码实测**：`spec` 前置未满足 **exit 1**；`tickets` 未 confirm **exit 1**；`stage` 缺 s3 **exit 1**（`MISS s3`）。技能说「拒绝」的地方一律按非 0 处理。
- **无人值守**：测试接缝（以及任何要人确认的地方）没人可答时，把问题 + 你的推荐答案写进交付说明的「本该问的问题」小节，按推荐继续并标注「自答」。

## 与 to-spec 的冲突裁定

| to-spec 的做法 | 本流程替换为 |
|---|---|
| 发布到 issue tracker、打 `ready-for-agent` 标签 | 写 `docs/specs/<slug>.md` + `dispatch confirm --by <你> --via card`；不要另建 tracker issue |
| 模板里没有 Delivery standard | 本流程必须补，拆票按它拆 |
| 故事长度、决策写法、测试决策 | **照抄不删**：这是审稿人和拆票的依据 |

## 上游锚点

- 底座：mattpocock/skills 的 `skills/engineering/to-spec`。
- 原技能更新后，复核三处：①测试接缝是否仍要求"与人确认" ②Implementation Decisions 的禁止项 ③Testing Decisions 三件套（好测试/模块/先例）。
