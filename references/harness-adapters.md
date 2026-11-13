# Harness 适配：能力槽 → 具体工具

技能正文只写**能力槽名**（`ask` / `shell` / `spawn_worker` / `spawn_once` / `list_workers` / `message` / `wait`），
由这份表决定在每个 harness 里落到哪个具体工具。**换 harness 时改这张表，不改技能。**

## 七个能力槽

| 槽 | 用来干什么 | 缺席时怎么办 |
|---|---|---|
| `ask` | 把结构化问题（含 options）交给用户，等答复 | 退化成正文里的问题 + 明确写「等你回答」；不许自己代答 |
| `shell` | 在本地跑命令（`dispatch` CLI、git、测试） | 没有就等于无法执行，直接说清 |
| `spawn_worker` | 起一个**具名、常驻**的执行者跑一段活，拿回结果；能再发消息（DSH 0.2.2-rc.3 起与 `spawn_once` 同一实现，见下方映射表） | 退到 `spawn_once`；再没有就走 solo：主代理自己做，文件里标「主代理代做」 |
| `spawn_once` | 起一个**无名、一次性**的执行者跑一段活，拿回结果后即结束；不占常驻名额 | 退到 `spawn_worker`，或走 solo 并标注「主代理代做」 |
| `list_workers` | 查当前有哪些执行者、叫什么 | 按「已知没有」处理（不要假装有） |
| `message` | 给某个执行者发消息（派活/追问/交叉评审） | 走文件交接：把内容写进文件，让执行者自己读 |
| `wait` | 等执行者结束 | `spawn_worker` 同步返回时不需要；异步时必须轮询或用完成通知 |

> **槽位会随 harness 版本合并（2026-11-13 实例）**：DSH 0.2.2-rc.3 把旧的独立 Team 名册并入 subagent 树，
> `spawn_worker` 与 `spawn_once` 在该 harness 上落到**同一个 `subagent` 工具**。
> 技能正文继续用槽名书写即可，映射由本表负责——这正是「换 harness 改表不改技能」的价值。

## 映射表

### DSH（DeepSeek Harness）—— 已核实（0.2.2-rc.3，2026-11-13 实测）

证据：会话内 `Object.keys(tools)` 返回 80 项；本机宿主 `app.asar/dsh/package.json` 版本 0.2.2-rc.3；
`@deepseek-ai/dsh-agent-team` 的 `src/index.ts` 里 `static Config` 与 `REMOVED_CONFIG_KEYS` 已直读。

| 槽 | 工具 | 备注 |
|---|---|---|
| `ask` | `ask_user_question` | 必带 `questions: [{id, header, question, options}]` |
| `shell` | `pwsh`，或 `run_code` 里 `child_process` | `run_code` 是唯一直接入口，其余工具都在 `tools.*` |
| `spawn_worker` | **已并入 `subagent`** | 0.2.2-rc.3 起 `spawn_teammate` 已移除：Team 不再有独立名册，成员就是 subagent 树上的节点。要「具名常驻 + 任务板」就直接起 `subagent`，再用 `team_task_*` 建任务 |
| `spawn_once` | `subagent`（或 `subagent_fork`，后者继承当前对话） | 返回 `{kind:"activation", subagentId}`，结束给「完成通知 + 最终回答」；每树并发 8、深度 1 |
| `list_workers` | `list_agents` | **返回整棵 subagent 树**（root + 全部后代），不再只列 teammate。旧 teammate 也在其中 |
| `message` | `send_message` | **参数名是 `agent`**（不是 `agent_id`）：`send_message({agent: "<name 或 session id>", message})`；inactive 目标会被唤醒 |
| `wait` | `wait_agent` | 返回 `{timedOut}` |

> **旧 Team API 已整体移除（2026-11-13 实测）**：`spawn_teammate` / `delete_teammate` / `rename_teammate` / `cleanup_team` 四个工具在 0.2.2-rc.3 的 80 项工具清单里**全都不存在**。
> `list_agents` 现返整棵树，`interrupt_agent` / `send_message` 都按 `agent` 参数工作（同一个字段名）。
> 旧的「两个 worker 槽不能互换」结论**作废**：现在没有两个槽——只有一套 subagent 树，`send_message`/`interrupt_agent` 对子智能体直接可用。
> 判据：**要任务板/来回沟通 → 起 `subagent` + `team_task_*`；只要一份报告 → `subagent` 不给任务板即可。**

> **配置侧（0.2.2-rc.3）**：`@deepseek-ai/dsh-agent-team` 的 `static Config` 只接受 `maxTasks`（默认 256）与 `defaultEnabled`（默认 false）。
> `maxMembers` / `maxMessageBytes` / `disposalTimeoutMs` 被 `REMOVED_CONFIG_KEYS` 硬编码拒绝——命中即抛 `TEAM_INVALID_CONFIG`，导致 preset 挂载失败（现象＝全部会话输入框「会话不可用」）。
> 依赖旧 roster 语义的本地插件（如 `dsh-agent-team-roster`）在新版下没有对应物，应注释停用。

### 千问办公 / QwenWork —— 已核实（本机 1.3.2-26101704，实测 2026-10-31）

证据：本机实测——`qw_query qwenwork.settings.skills` 识别技能 + 完整跑通 T1–T7 单票流程 + team 模式。详见 `docs/verification/2026-10-31-v1.16-qwenwork-eval.md`。

| 槽 | 工具（实际 API 名） | 备注 |
|---|---|---|
| `ask` | `AskUserQuestion` | 支持多问题 + 多选项 + multiSelect；旧文档写的 `question` 是内部 action 名，非对外 API 名 |
| `shell` | `Bash` | Git Bash 环境；cwd 跨命令会重置到工作目录，需用绝对路径或每次 `cd` |
| `spawn_worker` | `Agent`（**一次性**，无名册） | 千问没有常驻成员概念，`list_workers` / `message` 都无；此槽只能用一次性调用**模拟**，见下方 → 注 |
| `spawn_once` | `Agent` | 参数 `subagent_type`（general-purpose / Explore / Plan）+ `prompt`；同步返回；同一条消息块内放多个调用即并行执行 |
| `list_workers` | **无** | 实测确认不可用 |
| `message` | **无** | 实测确认不可用；brief / prompt 须一次性自包含全部指令 |
| `wait` | **无**（`Agent` 同步返回） | 不需要单独等 |

→ 单票执行完整通过（T1–T7，7/7）。team 模式用并行 `Agent` 调用即可实现，**不需要降级为 solo**（此前"缺 list_workers/message 故 team 必须走 solo"的推论已被实测推翻）。
→ 注：千问的"team 模式"是**用一次性 `Agent` 并行模拟**的——没有名册、没有 inbox、不能中途改派，交叉评审只能靠文件交接。需要真·常驻成员时改在 DSH 侧跑。
→ 状态机注意：`render` 后 ticket 处于 `claimed`，必须先 `dispatch start <id>` 推进到 `running`，`verify` 才接受。

### Claude Code —— 未在本仓库核验

按公开文档的常见命名填写，**首次使用前请用该 harness 的工具列表自行确认**：

| 槽 | 工具（待确认） |
|---|---|
| `ask` | `AskUserQuestion` |
| `shell` | `Bash` |
| `spawn_worker` | 无（`Task` 是一次性的） |
| `spawn_once` | `Task` |
| `list_workers` | 无（用 Team 相关工具，若有） |
| `message` | 无（用文件交接） |
| `wait` | 无（`Task` 同步返回） |

### Codex —— 未在本仓库核验

| 槽 | 工具（待确认） |
|---|---|
| `ask` | 无（文本提问） |
| `shell` | `shell` |
| `spawn_worker` | 无 → 退 `spawn_once`，再没有就 solo 降级 |
| `spawn_once` | 无 → solo 降级 |
| `list_workers` | 无 |
| `message` | 无（`references/codex-handoff.md` 的工单文件交接） |
| `wait` | 无 |

## 怎么用

1. 开工前确认本 harness 那张表：`ask` / `shell` 有就等于能跑完整流程；两个 worker 槽都没有才走 solo。
2. **先问要哪种 worker**：要名册 / 共享任务板 / 中途来回沟通 → `spawn_worker`；只要一份结果回报（调研、跑测试、查资料、全量 verify）→ `spawn_once`。派**执行票**给一次性执行者时，票的状态与证据仍由 Lead 用 `dispatch` 记，不指望执行者自己写账。
3. 不要用「系统提示里没写」当结论——用该 harness 的工具发现方式实测一次（DSH 是 `Object.keys(tools)`，千问办公看工具面板，其他看各自的 `/tools` 或等价入口）。
4. 填一张新表：照上面四节的格式加一节，并在本文件顶部登记「已核实 / 未核验」。
5. 注意 harness 的 shell 安全策略：千问办公的 `Bash` 拦截 `rm` / `rmdir` 等永久删除命令（返回 `SAFE_DELETE_REQUIRED`），清理需改用 `host_safe_delete` 移入回收站。dispatch 流程本身不删文件，但搭建/清理测试环境时会碰到。
