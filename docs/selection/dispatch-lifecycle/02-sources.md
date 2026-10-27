# 搜索取证: 派单生命周期技术选型
（角色 search-scout · 2026-10-22 · lead 代跑）

> 通道：外网文档不可达（r.jina.ai 超时）。以下全部为**本机文件直读 + 本机实测**。

| # | 事实 | 来源 | 抓取日期 | 状态 |
|---|---|---|---|---|
| 1 | gstack lease 记录 pid 的 start identity；`live` 打印 `<pid> <age>m <command>` | `gstack-main/bin/gstack-lease` 头部注释 | 2026-10-22 | 证实 |
| 2 | gstack lease 超 120 分钟自动 prune | 同上（"leases older than 120 min are pruned"） | 2026-10-22 | 证实 |
| 3 | pty 租约是 sessionId → expiresAt，到期拆会话 | `gstack-main/browse/src/pty-session-lease.ts` 注释 | 2026-10-22 | 证实 |
| 4 | ruflo projection 明确定位为"从记录派生" | `ruflo-main/plugins/ruflo-cost-tracker/scripts/projection.mjs` 头部 METHOD | 2026-10-22 | 证实 |
| 5 | DSH 团队上限 8，inactive 仍占位 | 本机实测：`spawn_teammate` 返回 `Team member limit 8 reached` | 2026-10-22 | 证实 |
| 6 | 子 agent 探索期不落盘，但工具调用在增长 | 6 份会话日志：调用 5/10/11/11/22/25 次，期间 run 目录无新文件 | 2026-10-22 | 证实 |
| 7 | Windows 上 pid 复用 / 进程身份是否可靠 | — | — | **未证实** |
| 8 | DSH 是否暴露 teammate 的 pid | — | — | **未证实** |

## 对选型的影响

- #1–#3 支持"seat 是带年龄的租约"；#4 支持"state 是投影、可重算"；
- #5/#6 是本项目实测：**判活必须看活动，不看产物**；
- #7/#8 决定 sweep **不自己杀**，只把数据报给人。
