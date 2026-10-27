# 团队名册：扩容与删除（Windows 实测，v1.0.1 按复现审查修订）

> 两件事：**名额不够**（默认 8）怎么办、**旧成员删不掉**怎么办。
> 全部在本机验证过；"外行照做会卡住"的四处已按 `doc-tester` 的审查补上。

## 一、名额：8 → 16

官方 `agent-team-profile` 把 `maxMembers` 写死成 **8**（基础包默认 16）。改 profile 补丁层即可：

```yaml
# ~/.dsh/profiles/desktop/cordis.patch.yml   ← 只改真正启用了 Agent Teams 的 profile
- id: agent-team
  name: "@deepseek-ai/dsh-experimental-agent-team"
  config:
    maxMembers: 16
    maxTasks: 256
    maxMessageBytes: 65536
    disposalTimeoutMs: 5000
```

**先确认该 profile 真的装了 Agent Teams**，否则写进去是静默无效：

```bash
python -c "import json,os; p=os.path.expanduser('~/.dsh/profiles/desktop/package.json'); print('agent-team' in open(p,encoding='utf-8').read())"
# True  → 这个 profile 是活的，改它
# False → 换另一个 profile（本机 desktop=True / web=False，web 改了没用）
```

- 改 `maxMembers` **不需要重启**（实测：写完第一次 `spawn_teammate` 就成功）。
- 验证门槛要算上 lead：`list_agents` 返回 **lead + N 个 teammate**。旧上限 8 时最多 9 行，所以**看到 10 行**才证明扩容生效。

## 二、删除：装 `dsh-agent-team-roster`

官方 roster **只增不减**（`TeamRoster` 没有 remove 方法；journal 只有 `team/member` 追加）。要删只能靠插件。

**插件**：`yezitotempeace/dsh-agent-team-roster`（v0.2.0）→ `delete_teammate` / `rename_teammate` / `cleanup_team`（只有 Lead 能调）。

### 1) 克隆

```bash
git clone --depth 1 https://github.com/yezitotempeace/dsh-agent-team-roster.git E:\beikong-code\dsh-agent-team-roster
```

### 2) 解 harness 依赖（Windows 特有）

插件的 `import "@deepseek-ai/dsh-experimental-agent-team"` 在 Windows 版里只存在于 `app.asar` 内，外部进程读不到 → 必须先解到真实目录。

**目标**：`E:\beikong-code\dsh-harness-root\node_modules\`（**目录本身必须叫 `node_modules`**，因为 Node 会把 junction 解析成 realpath）。

**正确的体积口径**（别拿错数字当"解坏了"的判据）：

| 对象 | 实测 |
|---|---|
| `app.asar` 本体 | **174.0 MB** |
| asar 内 `dsh/node_modules` 顶层条目 | **194**（按展开的包算是 549） |
| 解包后 `dsh-harness-root\node_modules` | **约 17,140 文件 / 401.5 MB** |
| 其中来自 `app.asar.unpacked` | **1,583 文件 / 243.4 MB** |

asar 头格式（自写脚本时用）：`u32[0]=4`、`u32[1]=payload 长度`、JSON 从**文件偏移 16** 开始；`数据基址 = 8 + payload 长度`；叶子有 `offset`（相对基址）+ `size`；`unpacked: true` 的文件从 `app.asar.unpacked\dsh\node_modules\<相对路径>` 取。

### 3) 两处 junction

```cmd
mklink /J "E:\beikong-code\dsh-agent-team-roster\node_modules" "E:\beikong-code\dsh-harness-root\node_modules"
mklink /J "%USERPROFILE%\.dsh\profiles\desktop\node_modules\dsh-agent-team-roster" "E:\beikong-code\dsh-agent-team-roster"
```

### 4) profile 登记

- `package.json` 依赖加 `"dsh-agent-team-roster": "link:E:/beikong-code/dsh-agent-team-roster"`
- `cordis.patch.yml` 追加：

```yaml
- insert:
    - id: agent-team-roster
      name: dsh-agent-team-roster
```

### 5) 重启（新增 bundle 行必须重启）

- **新增 insert 行需要重启**：实测重启前工具 46 个、重启后 49 个。改 `maxMembers` 才是不用重启的那一项。
- 0.2.1-rc.3 里**没有** `patchReload` 这个键（全树 0 命中），别照抄老文档。
- 点 × 只是进托盘，要**完全退出进程**再打开。

### 6) 验证

```
工具数 46 → 49，多出：delete_teammate / rename_teammate / cleanup_team
```

实测返回：

```js
delete_teammate({ target: 'pw03-pages-smoke' })
// → {"name":"pw03-pages-smoke","previousStatus":"inactive","releasedTasks":[],"discardedMessages":[]}
// 成员数减 1；可以用同名重新 spawn（名字真的释放了）
rename_teammate({ target: 'probe-temp', new_name: 'probe-renamed' })
// → {"previousName":"probe-temp","name":"probe-renamed","status":"running"}
```

## 三、删除语义与危险点

| 动作 | 真实语义 |
|---|---|
| `delete_teammate` | **会中断正在跑的回合**，丢弃未投递消息，释放名下任务与名字；不可撤销 |
| `rename_teammate` | 原地改名，保留历史/会话/任务/未投递消息 |
| `cleanup_team { scope: "teammates" }` | 判据是"**当前没有回合在跑**"——空闲成员都在射程内，**包括闲置的职能队友** |
| `cleanup_team { scope: "all" }` | 除成员外还会删**已完成的任务** |

所以：**要留职能队友，就逐个 `delete_teammate`，不要用 `cleanup_team`。**

## 四、回滚（有坑）

⚠️ 删掉 insert 行**不会撤销已写入的事件**：journal 里还留着 `phase: "removed"` / `renamedTo`，上游 schema 不认这两个字段，那个团队的投影会冻坏。

所以回滚只在"这个会话的团队可以不要了"时做：

1. 用备份覆盖 `cordis.patch.yml` / `package.json`（`.bak-roster-plugin-*`）
2. 删两处 junction
3. 重启，并**新开会话**（不要回到那个被改过 roster 的会话）

## 五、什么时候动这套

| 症状 | 做法 |
|---|---|
| `Team member limit 8 reached` | 改 `maxMembers`（第一节） |
| 表格里一堆用不上的旧成员 | 装插件后逐个 `delete_teammate`（第二节） |
| 成员名字取错了但想保历史 | `rename_teammate` |
| 要建第 N 个职能队友但名额满 | 先扩容，再 spawn |

## 六、这次审查发现的错（留痕）

| 原文 | 实际 |
|---|---|
| "解出 158MB" | 174MB（asar 本体）/ 401.5MB（解包后）/ 1,583 文件 243MB（unpacked） |
| "`patchReload: startup`，必须真退进程" | 该键在 0.2.1-rc.3 **不存在**；需要重启的是**新增 bundle 行** |
| "`list_agents` 数到 9 个即生效" | 含 lead，要到 **10 行**才证明 |
| "两个 profile 都写" | web profile 没有 Agent Teams 依赖，写进去静默无效 |
