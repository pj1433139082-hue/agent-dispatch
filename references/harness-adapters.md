# Harness 适配：能力槽 → 具体工具

技能正文只写**能力槽名**（`ask` / `shell` / `spawn_worker` / `list_workers` / `message` / `wait`），
由这份表决定在每个 harness 里落到哪个具体工具。**换 harness 时改这张表，不改技能。**

## 六个能力槽

| 槽 | 用来干什么 | 缺席时怎么办 |
|---|---|---|
| `ask` | 把结构化问题（含 options）交给用户，等答复 | 退化成正文里的问题 + 明确写「等你回答」；不许自己代答 |
| `shell` | 在本地跑命令（`dispatch` CLI、git、测试） | 没有就等于无法执行，直接说清 |
| `spawn_worker` | 起一个**独立上下文**的执行者跑一段活，拿回结果 | 走 solo：主代理自己做，文件里标「主代理代做」 |
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
| `spawn_worker` | `spawn_teammate` | `context: "fresh"` 才是干净上下文 |
| `list_workers` | `list_agents` | 判据：能调它才算有队友 |
| `message` | `send_message` | 给 target 发；inactive 目标会被唤醒 |
| `wait` | `wait_agent` | 返回 `{timedOut}`；超时后要重新 `list_agents` |

### 千问办公 / QwenWork —— 已核实（本机 1.3.2-26101704）

证据：`resources/agent-sdk/prompts/opencode.md` 的工具清单 + 运行时包 `flash-cli-acp.mjs` 里的工具描述文本。

| 槽 | 工具 | 备注 |
|---|---|---|
| `ask` | `question` | 运行时权限里以 `action:"question"` 出现 |
| `shell` | `bash` | |
| `spawn_worker` | `task` | 描述原文：「Launch a new agent…you must specify a `subagent_type` parameter」 |
| `list_workers` | **无** | 包里搜 `list_agents` 零命中 |
| `message` | **无** | 包里搜 `send_message` 零命中 |
| `wait` | **无**（`task` 同步返回） | 不需要单独等 |

→ 单票执行（render/verify/review/land）可完整跑；grill 的 team 模式必须走 solo 降级。

### Claude Code —— 未在本仓库核验

按公开文档的常见命名填写，**首次使用前请用该 harness 的工具列表自行确认**：

| 槽 | 工具（待确认） |
|---|---|
| `ask` | `AskUserQuestion` |
| `shell` | `Bash` |
| `spawn_worker` | `Task` |
| `list_workers` | 无（用 Team 相关工具，若有） |
| `message` | 无（用文件交接） |
| `wait` | 无（`Task` 同步返回） |

### Codex —— 未在本仓库核验

| 槽 | 工具（待确认） |
|---|---|
| `ask` | 无（文本提问） |
| `shell` | `shell` |
| `spawn_worker` | 无 → solo 降级 |
| `list_workers` | 无 |
| `message` | 无（`references/codex-handoff.md` 的工单文件交接） |
| `wait` | 无 |

## 怎么用

1. 开工前确认本 harness 那张表：`ask` / `shell` 有就等于能跑完整流程；`spawn_worker` 没有就走 solo。
2. 不要用「系统提示里没写」当结论——用该 harness 的工具发现方式实测一次（DSH 是 `Object.keys(tools)`，千问办公看工具面板，其他看各自的 `/tools` 或等价入口）。
3. 填一张新表：照上面四节的格式加一节，并在本文件顶部登记「已核实 / 未核验」。
