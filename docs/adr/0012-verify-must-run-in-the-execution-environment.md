# ADR-0012 Verify 必须在执行环境里一次跑通（远端事实走快照）

- 状态：Accepted（2026-10-25，grill-with-docs）——D1/D2 已实现（v0.89），D3 起的边界仍待拷问
- 触发：会话 `session-8516e665`（ts-sweep-server）。票 02 的 Verify 是 `ssh plant01 ...`，而执行端沙箱挡住了 `ssh.exe`：verify 连续 6 次报 `command 1: exit code 3`，两次 `retry` 都无效，最后要甲方把命令粘进自己的终端才算完。

## 1. 观察

- 失败不是"代码写错了"，是**判据在错误的机器上执行**：执行端没有 ssh、没有远端凭据、没有网络。
- `retry` 只能把状态拉回 running，**不会改变执行环境**，所以对这类失败天然无效。
- 框架没有"同样的失败又来了"的识别，只有一次次的 `VERIFY command 1: exit code 3`。

## 2. 决策

### D1 判据的四条硬要求（写票时）

1. **本机可跑**：不依赖 ssh / 远端机器 / 浏览器 / 登录态。
2. **幂等**：连跑两次结果一致。
3. **无网络**：不在 Verify 里下载、打 API。
4. **快**：单条 < 5 分钟。

### D2 远端事实快照化

需要远端事实时，由执行端在**独立步骤**里取一次，落成 `evidence/<host>-<what>-<timestamp>.txt`；Verify 只断言这个快照（存在 + 关键字段 + 时间戳新鲜度）。

### D3 重复失败要说话

`verify` 每次失败写 `verify-history.jsonl`；同一组错误出现第 3 次时打印 `VERIFY repeated failure: … Re-running will not change it — fix the environment the command needs, or rewrite the criterion.` 并保持 exit 1（不自动重试、不自动改票）。

## 3. 拷问后补的四条（2026-10-25 甲方「按推荐」）

- **D4 lint 只警告不拦**：Verify 里出现 `ssh ` / `scp ` / `curl ` / `wget ` / `http(s)://` → `WARN network_verify`；`lint` 仍 exit 0。理由：本机 `curl localhost` 是合法的，error 会误杀。
- **D5 票面加 `Requires:`**（`local` / `network` / `ssh` / `browser`，默认 `local`）：v1 只解析 + 警告（`environment_needed` / `invalid_requires`），不做硬门。
- **D6 `retry --reason` 变必填**：事后要能看出"为什么又试一次"。
- **D7 命令表自动生成**：`scripts/gen_command_table.py` → `docs/commands.md`，测试 `--check` 比对，漂移即红。

## 4. 影响

- 这四条要不要进 `lint`（error 还是 warning）？
- 快照的新鲜度怎么判、谁负责刷新？
- 执行端"能力清单"（有没有 ssh / 网络 / 浏览器）要不要变成票面字段？
- `retry` 是否需要区分"代码没改"与"环境没变"？

## 4. 影响

- 票面写 `ssh …` / `curl …` 的，从此视为**票的缺陷**，不是执行端的缺陷。
- 执行端不需要为了一张票去装 ssh 客户端或要凭据。
- 失败次数与失败指纹成为可查证据（`verify-history.jsonl`），复盘不再靠记忆。
