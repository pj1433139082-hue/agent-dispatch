# ADR-0021 Agent Teams 并入 subagent 树：dispatch 的适配与撤销

- 状态：Accepted（2026-11-13，实测 0.2.2-rc.3）
- 触发：宿主升级到 DSH 0.2.2-rc.3 后，本地 `cordis.patch.yml` 里基于旧 roster 的 `agent-team` override 与 `dsh-agent-team-roster` 插件失去对应物；同时 dispatch 仓有 82 处按旧模型书写的指令，会把执行端引向已不存在的工具。

## 1. 事实（源码直读 + 实测，均为一手）

宿主 `app.asar/dsh/package.json` 版本 **0.2.2-rc.3**。

**包结构变化**（`app.asar/dsh/node_modules/@deepseek-ai/` 实查）：

| 旧 | 新 |
|---|---|
| `dsh-experimental-agent-team` | **不存在**；已更名 `dsh-agent-team`，另拆 `dsh-tool-agent-team`、`dsh-client-ui-agent-team` 均已内置 |

**配置 schema**（`dsh-agent-team/src/index.ts` 直读）：

```ts
const REMOVED_CONFIG_KEYS = ['maxMembers', 'maxMessageBytes', 'disposalTimeoutMs'] as const

static Config: z<Config> = z.object({
  maxTasks: z.number().step(1).min(1).default(256),
  defaultEnabled: z.boolean().default(false),
})
```

构造函数对三个移除键做 `Object.hasOwn` 检查，命中抛 `TEAM_INVALID_CONFIG`。
**后果**：preset 挂载失败 → 全部会话输入框「会话不可用」。所以旧 override 必须整块去掉，不能只删一个键。

**工具面变化**（本会话 `Object.keys(tools)` 返回 80 项）：

| 旧工具 | 现状 |
|---|---|
| `spawn_teammate` | **已移除** |
| `delete_teammate` / `rename_teammate` / `cleanup_team` | **已移除** |
| `subagent` / `subagent_fork` | 保留，成为唯一的成员创建路径 |
| `list_agents` | 保留，语义变为**返回整棵 subagent 树** |
| `send_message` / `interrupt_agent` | 保留，参数统一为 **`agent`** |
| `team_task_*`（4 个） | 保留，任务板能力仍在 |

> 实测细节：给 `send_message` 传 `agent_id` 会报 `missing required property "agent"`——参数名是 `agent`。

## 2. 决策

**D1 配置侧：恢复 `agent-team` override，只留新版接受的键。**
不做「不要这个插件」的选择，因为 `maxTasks` 是真实需要的上限，且新版明确支持。

```yaml
- id: agent-team
  name: "@deepseek-ai/dsh-agent-team"
  config:
    maxTasks: 256
```

**D2 停用 `dsh-agent-team-roster`。** 它依赖旧 roster API，新版无对应物；强挂会让 preset 挂载失败。整块注释而非留 `disabled: true`，因为包名解析本身在旧体系下才成立，注释更明确。

**D3 dispatch 继续用能力槽书写，只改映射表。** 这正是 `references/harness-adapters.md` 的设计价值：技能正文写 `spawn_worker` / `spawn_once`，落到哪个具体工具由映射表决定。新版把两个槽合并到同一个 `subagent`，只需改表，技能逻辑不动。

**D4 诚实记录能力降级。** 旧模型有「名额上限可调」「可删除成员」「名字永久占用」三件事，新模型都没有。dispatch 的文档不能假装这些还在：

| 旧能力 | 新现实 | dispatch 的处置 |
|---|---|---|
| `maxMembers` 调到 16 | 无此键；人数受每树并发 8、深度 1 约束 | 文档改为「分多棵树」，删掉扩容教学 |
| `delete_teammate` 删成员 | 无删除工具；subagent 结束即释放 | 删掉相关操作指引 |
| 名字永久占用、roster 只增不减 | 名字即 agent 路径，随树存续 | 删掉「名字永久占用」的告诫 |

## 3. 影响面与处置（dispatch 仓）

| 文件 | 处置 |
|---|---|
| `references/harness-adapters.md` | DSH 节整节重写：槽表加版本提示、映射表改 `subagent`、作废旧「两槽不能互换」结论、补配置侧限制 |
| `docs/team/roster-setup.md` | 整篇重写为「已作废」说明，保留链接不 404，写清作废原因与正确配置 |
| `SKILL.md` | 名额/删除段重写；表格两行改措辞；正文改回槽名（不直书工具名） |
| `GLOSSARY.md` | `fresh 实例` 定义改 subagent；`roster` 条目标已作废 |
| `flow-skill/SKILL.md` | 阶段边界去掉 `teammate`；派活行改为「subagent + 任务板」 |
| `grill-skill/SKILL.md` | 称呼统一为「子智能体」 |
| `docs/adr/0013` | 加「部分被取代」标注，指明角色划分仍有效、roster 机制失效 |
| `tests/test_harness_slots.py` | 去掉 `spawn_teammate` 断言；「两槽不能互换」改为「槽位可合并」 |
| `tests/test_docs_sections.py` | 旧文档内容断言（`174.0 MB`/`10 行`/`cleanup_team`）换成新事实断言（`REMOVED_CONFIG_KEYS`/新包名/旧包名不得出现） |

## 4. 后果

- **正面**：宿主不再因旧 override 挂载失败；dispatch 的指令与实际工具一致；能力槽抽象被验证是有效的（一个 harness 大改只需改映射表）。
- **负面**：失去可调名额与成员删除能力；多智能体协作的并行度上限从「16 名常驻成员」降为「每树 8 个并发子智能体」。
- **未改变**：任务板（`team_task_*`）仍在，判据级证据、写域、异体评审等 dispatch 核心门禁完全不受影响。

## 5. 未证实

- 新版 Team 面板是否仍显示成员列表：客户端 UI 走 `dsh-client-ui-agent-team`，本轮只验了工具面与配置面，未开面板看。
- 多棵树并行时任务板是否隔离：`agentTeams` 服务以 root Session 为 Team 边界（`rootOf(caller)`），理论上隔离，未做实证。
