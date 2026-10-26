# 团队：八个职能队友

> 来自 ADR-0013。**按职能分，不按项目分**——`executor` 能接任何票，不像 "Frontend Developer" 只能做前端。

## 阵容

| # | 名字 | 职能 | 什么时候用 | 产出 |
|---|---|---|---|---|
| 1 | `scout` | 侦察取证 | 开工前查事实、查开源参照、查版本 | 结论 + 证据（文件:行 / URL + 日期） |
| 2 | `planner` | 拆票排期 | 有规格但没票，或票的写域/依赖乱了 | 票 + 波次表 |
| 3 | `executor` | 按票执行 | 票已就绪、要有人动手 | 改动 + receipt |
| 4 | `verifier` | 独立验收 | 执行完，要判断"真做完了吗" | pass/fail + 变异检查结果 |
| 5 | `reviewer` | 异体评审 | 要另一个视角读 diff | verdict + findings |
| 6 | `auditor` | 对抗审查 | 方案/ADR/门禁要压力测试 | ≤7 条假设与反例 |
| 7 | `fixer` | 排障 | 有明确失败现象要定位 | 复现 + 根因 + 最小修复 + 回归测试 |
| 8 | `scribe` | 文档交付 | 要写报告/ADR/交接稿 | 可复现的 Markdown |

## 一句话分工

```
scout  → 事实          planner → 计划        executor → 产物
verifier → 证据         reviewer → 盲区      auditor → 失败方式
fixer  → 根因           scribe   → 交接
```

## 三条硬规矩（ADR-0013）

1. **常驻 8 个，重活派 fresh 实例**：常驻成员的上下文会腐烂；重要任务用 `spawn_teammate(context:"fresh")`，用完即删。
2. **队友是手，dispatch 是账**：teammate 产出"结论/证据/改动"，票的状态、verify、land 一律由 Lead 用 `dispatch` 管。
3. **派活要写"边界"**：每次派活明确"只准动哪些文件 / 只准读不准写 / 回复只给几行"，否则队友会顺手改别的。

## 边界（谁不看什么）

| 角色 | 只看 | 明确不看 |
|---|---|---|
| `auditor` | 执行前文本：spec / ADR / 票面 / 判据 | **不看 diff**（那是 reviewer） |
| `reviewer` | `review-packet.md`（票 + diff + 回执 + verify） | 不看需求原文 |
| `verifier` | 跑 Verify、抽查证据、临时副本里做变异检查 | **不写账**（receipt / verify / state） |
| `fixer` | 票外/线上故障 | **不接票内 bug**（票内归 executor） |
| `scribe` | 跨会话 handoff | 不重复写 `closeout` 已经生成的单票报告 |

## 两个已知缺口（ADR-0013 §4）

1. **没有集成者**：`land --wave` 每票各建一条 `dispatch/land/<run-id>` 分支，互相不包含；两张各自绿的票合进 main 才炸。需要"落地后在同一棵树上跑一次全量 Verify"。
2. **没有判据评审**：`weak_verify` 只认 `echo ok / print(1)` 字面量。`Verify: test -f out/report.md` 这种"存在即通过"的判据能骗过 lint + verify + 变异检查。

## 与 dispatch persona 的关系

| 队友 | 对应 persona（S2 选型角色 / 执行人设） |
|---|---|
| `scout` | `oss-scout` + `search-scout`（合并） |
| `auditor` | `adversary` |
| `planner` | `dispatcher` |
| `reviewer` | 无（评审人由 `dispatch review --reviewer` 指定） |
| `executor` / `verifier` / `fixer` / `scribe` | `domain-owner` / `cost-keeper` 按领域挑 |

## 名额与删除

- 名额默认 8（官方 profile）→ 要更多改 `maxMembers`（实测不用重启）
- 旧成员删不掉 → 装 `dsh-agent-team-roster`，用 `delete_teammate` 逐个删
- 全部步骤与回滚：`docs/team/roster-setup.md`

## 派活模板

```text
角色：{scout|planner|executor|verifier|reviewer|auditor|fixer|scribe}
任务：一句话说清要做成什么（可验收）。
边界：只准动 X；只准读不准写；不改票。
交付：文件路径 + 回复里只给 N 行摘要。
```

角色卡正文见 `docs/team/roles/*.md`（spawn 时把对应那份塞进 prompt）。
