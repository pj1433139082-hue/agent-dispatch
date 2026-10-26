# ADR-0013 八职能队友：按职能分、常驻 + fresh 实例、手账分离

- 状态：Accepted（2026-10-25，grill-with-docs，甲方「按推」）
- 触发：本工作区团队面板里 8 个名额被 6 个泵工作台遗留成员 + 2 个通用 scout 占满，`spawn_teammate` 直接报 `Team member limit 8 reached`；且 `search-scout` 以"只写一个文件"的人设约束拒绝了跨项目任务。根因是**用领域人格当常驻劳动力**。

## 1. 调研

| 项目 | 模型 | 结论 |
|---|---|---|
| Agency Agents（200 人格） | 纯人格库：Identity / Process / Deliverables / Success Metrics，无编排 | 人格写法借鉴；**不采用**领域常驻 |
| GetShitDone（33 Agent） | **按职能分**（researcher/planner/executor/verifier/auditor/doc-writer/debugger），每个在**全新 200K 上下文**跑，波次并行 | **采用**职能划分 + fresh 上下文 |
| Gstack / Archon | 命令工具箱 / YAML DAG | 编排过重，不采用 |

## 2. 决策

### D1 按职能分，不按领域分

八个常驻职能：`scout` `planner` `executor` `verifier` `reviewer` `auditor` `fixer` `scribe`。
理由：瓶颈在环节（谁查、谁做、谁验、谁审），不在领域；领域差异用 prompt 里的上下文补。

### D2 常驻 8 个 + 重活派 fresh 实例

常驻成员只接轻活（查一下、看一眼）；重要任务用 `spawn_teammate({context:"fresh"})`，任务完即删——常驻成员上下文会腐烂（GSD 的 context rot）。

### D3 队友是手，dispatch 是账

teammate 只产出结论/证据/改动；票状态、`verify`、`review`、`land` 一律由 Lead 用 `dispatch` 管。禁止让 teammate 自己写 `receipt.json` 或改 `state.json`。

### D4 派活必须写边界

每次派活三件套：**任务**（可验收）、**边界**（只准动哪些文件 / 只读）、**交付**（路径 + 摘要行数）。

### D5 角色卡随包分发

`docs/team/roles/*.md` 八份 + `docs/team/README.md` 阵容与派活模板，随技能包分发。

## 3. 影响

- 团队面板从"项目常驻班子"变成"职能班组"：任何项目的活都能派。
- 跨项目不再串味：领域信息写在任务 prompt 里，不写进人格。
- 名额管理有纪律：重活 fresh 实例用完即删，常驻只留 8 个职能。

## 5. 外部事实核对（2026-10-26，官方文档 + 社区插件）

**官方文档（deepseek-harness / packages/experimental/agent-team/README.zh.md）**：

- `maxMembers` 在基础包里默认 **16**，但官方 **agent-team-profile 把它配成 8**（社区 optimizer 的 README 明写）。
- **“teammate 名字是永久的——即使创建失败的 teammate 也保留其名字，任何名字都不会被复用”**。
- 也就是说：**没有“移除成员”这个能力**，roster 是只增不减的；这不是 bug，是设计。

**社区插件（两条现成路）**：

| 插件 | 做什么 | 与本 ADR 的关系 |
|---|---|---|
| `Soulize/dsh-agent-teams-optimizer` | 把 `maxMembers` 调大（默认 16，任意正整数），改的是 `spawn_teammate` 真正检查的数 | 解决“8 个不够”，不解决“删不掉” |
| `zws20070309/dsh-dispatch-agent-team` | 12 个流程角色（外部调研/探索调研/前沿审查/计划审查/执行落地/集成落地/复现回归/逻辑审查/对抗审查/美术审查/反思优化/文档术语）+ `report_result` 结构化汇报 + 队员能力面自动收窄 + `/team` 按会话开关 + 缓存友好 | **和本 ADR 同一路线**，且更完整；我们的 8 个职能可视为它的子集 |

**结论**：ADR-0013 的 D1–D5 方向与社区实践一致；落地方式二选一：

1. 自建 8 职能（本 ADR），并把 `maxMembers` 调到 ≥16（装 optimizer 或改 profile）；
2. 直接采用 `dsh-dispatch-agent-team` 的 12 角色，把我们的角色卡当它的“角色补充说明”。
## 4. 未定

- 常驻成员上下文清理：DSH 没有"清空成员上下文"的接口，只能靠 fresh 实例；常驻成员的长会话风险未量化。
- 角色卡与 `dispatch assign --persona` 的对照目前是手工表（README），要不要做成机器可读的 `roles.json` 待定。
