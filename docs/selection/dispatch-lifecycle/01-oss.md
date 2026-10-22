# 开源借鉴侦察: 派单生命周期技术选型
（角色 oss-scout · 2026-10-22 · lead 代跑）

## 要回答的问题与判据

问题：seat（名额）/ sweep（判活）/ repair（索引重建）三件事，业界用什么形状。
判据：① 不引入外部服务；② 判活基于可观测事实而不是猜；③ 索引可重建；④ 零第三方依赖。

## 参照 1：gstack `bin/gstack-lease`（bash，本机副本）

- 位置：`D:\obsidian_work\cangku\paper_work\资料库\AI工具\gstack\gstack-main\bin\gstack-lease`
- 做法：lease 写在共享 checkout 的 git 目录（`<git dir>/gstack-leases/<pid>`），记录 pid 的 start identity；`touch` 续租，`live` 列出活进程持有的 lease 并打印 `<pid> <age>m <command>`；超过 120 分钟的 lease 自动 prune；有活进程持锁时 touch 退出 3。
- 借鉴：**lease + 年龄 + live 列表**三件套，"年龄"是一等字段。
- 不采用：bash + pid 语义（Windows 上 pid 复用与进程身份判定不可靠）。

## 参照 2：gstack `browse/src/pty-session-lease.ts`

- 做法：身份（sessionId）/ 秘密（attachToken）/ 租约（sessionId → expiresAt）三件事分开；**租约到期即拆会话**。
- 借鉴：seat 本质是**带 TTL 的租约**，过期即可回收，不必判断"它是不是死了"。
- 不采用：token 生命周期细节（与本项目无关）。

## 参照 3：ruflo `plugins/ruflo-cost-tracker/scripts/projection.mjs`

- 做法：文件头 METHOD 写清"读 session 记录再算"，即**投影是从事实源派生的视图**。
- 借鉴：`state.json` 就是投影；repair 从 `runs/*/run.json` 重算是正解，不是"修复损坏文件"。

## 结论三态

**建议采用** lease-TTL + projection-rebuild 两个形状：seat = 带年龄的租约列表；sweep = 只读三列（年龄 / 最后活动 / 是否已有回执）；repair = 从 runs 重算索引、冲突交人裁决。

## 未证实

- Windows 上"进程 start identity"的可靠判定（gstack 用 pid + 命令行，本机未实测）；
- DSH 是否暴露 teammate 的 pid（未查到接口）。
