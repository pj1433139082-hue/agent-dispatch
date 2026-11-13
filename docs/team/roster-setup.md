# 团队名册：已随 DSH 0.2.2-rc.3 作废

> **状态：整篇失效（2026-11-13）。** 本文原讲两件事——把 roster 名额从 8 扩到 16、以及装插件删除旧成员。
> 这两件事在新版 DSH 里**都没有对应物**，因为「独立 Team 名册」这个模型被移除了。
>
> 保留本文是为了让旧链接不 404，并说明为什么它不再适用。**不要照着做。**

## 为什么作废

DSH 0.2.2-rc.3（对应宿主内置升级指南 `upgrade-guide/v0.2.1-rc.2/agent-team-subagents`）把 Agent Teams 重构了：

| 旧模型 | 新模型 |
|---|---|
| 独立 Team 体系，有自己的 roster / 邮箱 | Agent Teams 建立在 **subagent 树**之上，成员就是树节点 |
| `spawn_teammate` 创建具名常驻成员 | 用 **`subagent`** 创建；名字即 agent 路径 |
| Team 作用域的 `send_message` / `list_agents` / `interrupt_agent` | 同一套工具，参数统一为 **`agent`** |
| roster「只增不减」，靠插件 `delete_teammate` / `rename_teammate` / `cleanup_team` 删除 | **这三个工具与 roster 概念一起移除** |
| `maxMembers` 上限（默认 8，可调 16） | **没有这个键**；人数由 subagent 树并发限制（每树 8）决定 |

## 配置侧：哪些键被拒绝（源码直读）

`@deepseek-ai/dsh-agent-team` 的 `src/index.ts`：

```ts
const REMOVED_CONFIG_KEYS = ['maxMembers', 'maxMessageBytes', 'disposalTimeoutMs'] as const

static Config: z<Config> = z.object({
  maxTasks: z.number().step(1).min(1).default(DEFAULT_MAX_TASKS),   // 256
  defaultEnabled: z.boolean().default(false),
})
```

构造函数里对三个移除键做 `Object.hasOwn` 检查，命中即抛 `TEAM_INVALID_CONFIG`。
**后果**：preset 挂载失败 → 全部会话输入框显示「会话不可用」。所以旧 override 必须整块去掉，不能只删其中一个键。

正确的做法（只保留新版接受的键）：

```yaml
# ~/.dsh/profiles/<启用了 agent-team 的 profile>/cordis.patch.yml
- id: agent-team
  name: "@deepseek-ai/dsh-agent-team"
  config:
    maxTasks: 256
```

## 名册管理插件：停用

`dsh-agent-team-roster`（提供 `delete_teammate` / `rename_teammate` / `cleanup_team`）依赖旧 roster API，
新版下没有对应物。应把它整块注释掉；强挂会让 preset 挂载失败。

要恢复类似能力，得按新 API 重写（subagent 树上的节点管理），不是改配置能解决的。

## 现在该怎么做「名额不够」

- 单棵树并发上限是 8，深度 1。需要更多并行时，**分多棵树**（起多个根 subagent），而不是调 roster 上限。
- 需要任务板协作：起 `subagent` 后用 `team_task_*` 四个工具建/查/改任务，写域用 `write_scopes` 声明。
- 具体映射见 `references/harness-adapters.md` 的 DSH 节（0.2.2-rc.3 已核实）。

## 历史记录

原文（v1.0.1，2026-10-26 扩容经验）已随本次重写删除，可从 git 历史取回：

```bash
git log --oneline -- docs/team/roster-setup.md
```
