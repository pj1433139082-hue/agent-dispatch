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
| `team_task_*`（4 个） | 保留，但**受 Team 模式门控**（`isEnabled`，默认关）——详见 §6.1 |

> 实测细节：给 `send_message` 传 `agent_id` 会报 `missing required property "agent"`——参数名是 `agent`。

## 2. 决策

**D1 配置侧：恢复 `agent-team` override，只留新版接受的键。**
不做「不要这个插件」的选择，因为 `maxTasks` 是真实需要的上限，且新版明确支持。`defaultEnabled` 必须设 `true`：不设的话任务板工具不注册（§6.1 实测），dispatch 的 `spawn_worker` 槽语义会失效。

```yaml
- id: agent-team
  name: "@deepseek-ai/dsh-agent-team"
  config:
    maxTasks: 256
    defaultEnabled: true   # 否则 team_task_* 不注册，见 §6.1
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
- **未改变（前提是 `defaultEnabled: true`）**：任务板（`team_task_*`）仍在，判据级证据、写域、异体评审等 dispatch 核心门禁完全不受影响。**注意**：任务板工具受 Team 模式门控，`defaultEnabled: false` 时它们根本不注册（§6.1 实测），所以「任务板还在」这句话只在开 Team 模式时成立。

## 5. 未证实

- 新版 Team 面板的 UI 呈现：只验了工具面与配置面，未在浏览器里开面板看。
- 多棵树并行时任务板是否隔离：`agentTeams` 服务以 root Session 为 Team 边界（`rootOf(caller)`），理论上隔离，未做实证。

## 6. 端到端实测（2026-11-13，起真实任务板会话）

只验工具签名与 YAML 语法是不够的；本节记录**真起会话**的结果，其中两个坑是纸面验证发现不了的。

### 6.1 任务板工具默认不注册

`team_task_*` 四个工具由 `ctx.agentTeams.isEnabled(agent)` 门控（源码 `{ when: ({agent}) => enabled(agent) }`），
而 `defaultEnabled` 默认 `false`。实测：`defaultEnabled: false` 时子会话里
`tools.team_task_list is not a function`；设为 `true` 后同一探针拿到全部 4 个工具。

**决策**：profile 配 `defaultEnabled: true`。否则任何「起子智能体后用任务板协作」的流程都会失败——
而 dispatch 的 `spawn_worker` 槽语义正依赖任务板。

### 6.2 工作区 ACL 授权失败导致 workspace-write 会话起不来（Win32 5）

首次探针会话在 `workspace-write` 模式下报：

```
sandbox-local: windows-acl workspace grant failed:
Win32Error: SetNamedSecurityInfoW failed (Win32 5):
grantWrite(E:\beikong-code\agent-dispatch)
```

根因是工作区目录缺少当前用户的 `WRITE_OWNER`（`WRITE_DAC` 有），沙箱无法 provision 工作区授权。
用 `diagnose-windows-sandbox-acl` 技能一次诊断+修复后（`writeOwner: false → true`、`GRANTED=1`、`verified`），
后续会话正常。**注意**：这不是 agent-team 的问题，是 Windows ACL 的独立缺陷，
但它的现象（会话不可用）与本 ADR 要修的「preset 挂载失败」极像，容易被误判。

### 6.3 提权请求的真实行为：策略决定一切（含一次 Lead 误判，已更正）

**先说结论**：提权不是「挂死」，也不是「自动拒绝」，而是**取决于会话的 `approvalState.policy`**。
源码 `dsh-user-approval/src/index.ts` 写得很明确：

```ts
// 'never' — never prompt anyone: every ask resolves 'rejected' deterministically.
if (this.effectivePolicy(session) === 'never') return 'rejected'   // 在 dispatch 之前短路
```

| policy | 提权请求的行为 | 实测观察 |
|---|---|---|
| `never` | **确定性地立即 `rejected`**（源码在 dispatch 前短路），不提示任何人 | 未复现「挂死」；此前那次是 `ask` 策略 |
| `ask` | 交给应答者（本机 `hooks/settings.json` 的 `approvalMode: dialog` = **真人弹窗**）；无应答者则 fail-closed `unavailable` | **一直等待，不自动超时**：实测 493 秒仍在 `pending_tools`，`turnOpen: true` |

**本机实际情况**：`approvalMode` 为 `dialog`，所以 `ask` 策略下的提权会**等真人点弹窗**。
用户确认：「是我同意之后手动改的」——即那次是**人工批准**后才变成 full-access 并写成功的。

**Lead 曾误判**：看到「`elapsed_sec` 涨到 1019 秒没返回」就写成「提权请求挂死 + `interrupt_agent` 无法终止」，
并据此声称 harness 缺陷——**这是错的**。那次会话后来 `result: succeeded`、完整输出 `SMOKE2-OK`，
提权确实生效（`WRITE_OK` / `READBACK: ok`）。等待时间是在等我批准。

**更正后的判定口径**（两次踩坑的教训）：判定子会话是否卡住，必须看
`approvalState.turnOpen`（`true` = 有回合没结束）与 `pending_tools` / `running_cmds`，
**并且区分「等批准」与「卡死」**——本机 `policy=ask` 下长时间不返回通常就是**在等人**，不是 bug。

**仍然成立的操作结论**：
- 工作区外路径在 `workspace-write` 下必然 EPERM（预期行为，不是缺陷）
- **给子会话的工单里不要请求提权**：`policy=never` 会被确定性拒绝（白费一次尝试），
  `policy=ask` 会一直等人（无人值守时等于卡住）。要么把路径纳入工作区，要么由父会话代写。
- 无人值守批量跑票时，应确认会话 `policy=never` 且工单里明确禁止 `sandbox_permissions`。

### 6.4 两个探针的终验（都成功）

**探针二**（ACL 修复后，`workspace-write` 起始、经一次提权完成跨目录写）—— `SMOKE2-OK`：

```
1) team_task_* 存在: team_task_create,team_task_list,team_task_get,team_task_update
2) team_task_list: {"tasks":[]}  → 调用成功，0 条任务（空板，非报错）
3) 工作区外写入: workspace-write 下 EPERM → 提权后 WRITE_OK / READBACK: ok
```

这一探针顺带证明了三件事：ACL 修复后 `workspace-write` 会话**能起来**；
`defaultEnabled: true` 后任务板工具**已注册**；提权**确实生效**（不是挂死）。

**探针三**（显式 `permission: danger-full-access`、只写工作区内）—— `SMOKE3-OK`：

```
1. TEAM: team_task_create,team_task_list,team_task_get,team_task_update — 4 个工具可用
2. TASKS: 0 — 共享任务板当前无任务
3. WRITE_OK: ok — 工作区写入/读取/删除均正常
```
