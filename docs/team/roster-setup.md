# 团队名册：扩容与删除（Windows 实测）

> 两件事：**名额不够**（默认 8）怎么办、**旧成员删不掉**怎么办。
> 两条都在 2026-10-26 真机验证过，命令与输出都来自本机。

## 一、名额：8 → 16

官方 `agent-team-profile` 把 `maxMembers` 写死成 **8**（基础包默认 16）。改 profile 补丁层即可：

```yaml
# ~/.dsh/profiles/<desktop|web>/cordis.patch.yml
- id: agent-team
  name: "@deepseek-ai/dsh-experimental-agent-team"
  config:
    maxMembers: 16
    maxTasks: 256
    maxMessageBytes: 65536
    disposalTimeoutMs: 5000
```

- **两个 profile 都写**，避免猜错当前用哪个。
- **实测不用重启**：写完第一次 `spawn_teammate` 就成功（原以为要重启，错了）。
- 验证：`list_agents` 数到 9 个以上成员即生效。

## 二、删除：装 `dsh-agent-team-roster`

官方 roster **只增不减**（`TeamRoster` 没有 remove 方法；journal 只有 `team/member` 追加）。要删只能靠插件。

**插件**：`yezitotempeace/dsh-agent-team-roster`（v0.2.0）→ `delete_teammate` / `rename_teammate` / `cleanup_team`。

### Windows 安装（依赖在 app.asar 里，必须解出来）

```bash
# 0) 克隆
git clone --depth 1 https://github.com/yezitotempeace/dsh-agent-team-roster.git E:\beikong-code\dsh-agent-team-roster
```

1. **解 harness 依赖**：把 `resources/app.asar` 里 `dsh/node_modules` 整棵解到真实目录，且该目录**本身必须叫 `node_modules`**：
   ```
   E:\beikong-code\dsh-harness-root\node_modules\        （本次 194 顶层包 / 158MB + 1583 个 unpacked 文件）
   ```
   asar 头解析：`u32[0]=4`、`u32[1]=payload 长度`、JSON 从**文件偏移 16** 开始，`数据基址 = 8 + payload 长度`；叶子有 `offset`（相对基址）+ `size`；`unpacked: true` 的文件从 `app.asar.unpacked\dsh\node_modules\<相对路径>` 取。
2. **插件目录建 junction**：`dsh-agent-team-roster\node_modules` → `E:\beikong-code\dsh-harness-root\node_modules`
   （Node 会把 junction 解析成 realpath，所以目标目录必须真的叫 `node_modules`，否则 `@deepseek-ai/*` 解析不到。）
3. **profile 建 junction**：`~/.dsh/profiles/desktop/node_modules/dsh-agent-team-roster` → 插件目录
4. **登记依赖**：profile `package.json` 加 `"dsh-agent-team-roster": "link:E:/beikong-code/dsh-agent-team-roster"`
5. **加 patch 行**：
   ```yaml
   - insert:
       - id: agent-team-roster
         name: dsh-agent-team-roster
   ```
6. **完全退出 DSH 再打开**（`patchReload: startup`；点 × 只是进托盘，主进程不退就不生效）。

### 验证装好了

```
工具数 46 → 49，多出：delete_teammate / rename_teammate / cleanup_team
```

实测记录：

```js
delete_teammate({ target: 'pw03-pages-smoke' })
// → {"name":"pw03-pages-smoke","previousStatus":"inactive","releasedTasks":[],"discardedMessages":[]}
// 成员数 17 → 16；名字可被同名 spawn 重新占用（真的释放了）
rename_teammate({ target: 'probe-temp', new_name: 'probe-renamed' })
// → {"previousName":"probe-temp","name":"probe-renamed","status":"running"}
```

### 危险点

```js
cleanup_team({ scope: "teammates" })   // 会删掉所有 inactive/failed 成员
```

**空闲的职能队友也是 `inactive`** —— 用它清遗留成员会把职能队一起删掉。要留队就**逐个 `delete_teammate`**。

### 回滚

删 `cordis.patch.yml` 里那 4 行 + profile `package.json` 的依赖 + `node_modules\dsh-agent-team-roster` junction，重启。

## 三、什么时候动这套

| 症状 | 做法 |
|---|---|
| `Team member limit 8 reached` | 改 `maxMembers`（第一节） |
| 表格里一堆用不上的旧成员 | 装插件后逐个 `delete_teammate`（第二节） |
| 成员名字取错了但想保历史 | `rename_teammate` |
| 要建第 N 个职能队友但名额满 | 先扩容，再 spawn |
