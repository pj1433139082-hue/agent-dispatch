# Harness 适配：能力槽 → 具体工具

技能正文只写**能力槽名**（`ask` / `shell` / `spawn_worker` / `spawn_once` / `list_workers` / `message` / `wait`），
由这份表决定在每个 harness 里落到哪个具体工具。**换 harness 时改这张表，不改技能。**

## 七个能力槽

| 槽 | 用来干什么 | 缺席时怎么办 |
|---|---|---|
| `ask` | 把结构化问题（含 options）交给用户，等答复 | 退化成正文里的问题 + 明确写「等你回答」；不许自己代答 |
| `shell` | 在本地跑命令（`dispatch` CLI、git、测试） | 没有就等于无法执行，直接说清 |
| `spawn_worker` | 起一个**具名、常驻**的执行者跑一段活，拿回结果；它进名册，可再发消息 | 退到 `spawn_once`；再没有就走 solo：主代理自己做，文件里标「主代理代做」 |
| `spawn_once` | 起一个**无名、一次性**的执行者跑一段活，拿回结果后即结束；不占名册、不占队位 | 退到 `spawn_worker`，或走 solo 并标注「主代理代做」 |
| `list_workers` | 查当前有哪些执行者、叫什么 | 按「已知没有」处理（不要假装有） |
| `message` | 给某个执行者发消息（派活/追问/交叉评审） | 走文件交接：把内容写进文件，让执行者自己读 |
| `wait` | 等执行者结束 | `spawn_worker` 同步返回时不需要；异步时必须轮询或用完成通知 |

## 映射表

### DSH（DeepSeek Harness）—— 已核实

证据：会话内 `Object.keys(tools)` 返回 60+ 项。

| 槽 | 工具 | 备注 |
|---|---|---|
| `ask` | `ask_user_question` | 必带 `questions: [{id, header, question, options}]` |
| `shell` | `pwsh`，或 `run_code` 里 `child_process` | `run_code` 是唯一直接入口，其余工具都在 `tools.*` |
| `spawn_worker` | `spawn_teammate` | 具名常驻，进 roster；`context: "fresh"` 才是干净上下文。上限 16 人，名字永久占用 |
| `spawn_once` | `subagent`（或 `subagent_fork`，后者继承当前对话） | 无名一次性：返回 `{kind:"activation", subagentId}`，结束给「完成通知 + 最终回答」；每树并发 8、深度 1 |
| `list_workers` | `list_agents` | 判据：能调它才算有队友。**只列 teammate，子智能体不在名册里** |
| `message` | `send_message` | 给 target 发；inactive 目标会被唤醒 |
| `wait` | `wait_agent` | 返回 `{timedOut}`；超时后要重新 `list_agents` |

> **两个 worker 槽不能互换（2026-11-01 实测）**：`send_message` / `interrupt_agent` / `team_task_update --reassign` 对子智能体的 `subagentId` 一律回 `active teammate "<id>" not found`——团队工具只认 teammate 名字。子智能体只能从「子智能体对话目录」（`palimpsest_list` 带 `includeSubagents`）看到；「可续聊」也只能走它自己的会话入口，别拿团队三件套去找它。
> 判据：**需要名册 / 任务板 / 来回沟通 → `spawn_worker`；只想要一份报告 → `spawn_once`。**

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
