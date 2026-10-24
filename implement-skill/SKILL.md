---
name: implement-dispatch
description: 按票执行：brief 审批 → render（一票一 worktree）→ 执行端动手 → verify 独立验收 → review 异体评审 → land 到 integration branch。触发：implement-dispatch、按票开发、派单执行、跑票、验收落地。
---

# 4/4 · Implement

上一步：**to-tickets-dispatch**（或直接拿现成的票进来）

## 单票流程

```bash
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py brief <id>                     # 填五段（理解/计划/要改的文件/风险/疑问）
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py brief <id> --approve <你>       # 不批，render 不放行（配置默认开）
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py render <id> --agent <执行者>     # 一票一 worktree，产出 work-order.md
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py start <id>
#   ← 执行端在这里干活（见下）
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py verify <id>                    # 复跑票上的 Verify，逐条对证据
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py review <id> --reviewer <另一人> --verdict pass    # L2+ 还要 --packet-hash
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py land <id>                      # 只建分支，不 push、不合并 main
```

## 回执长什么样（照这个写）

- `criteria` 的 `id` 必须**正好覆盖**票面 `## Acceptance` 的 `1..N`，多一条少一条都判失败
- 证据只有 5 种：`file`（run 目录或 worktree 相对路径）/ `inline` / `absent` / `command` / `note`
- **只有 `note` 一条证据** → 整票判 `degraded`（verify 退出码 2），还得 `review --accept-degraded` 才能往下走
- 完整 schema 在 `references/ticket-contract.md`，每次 `render` 也会写进 `work-order.md` 的 `## Receipt contract`

## 两条硬规矩（实测踩过）

1. **回执写 run 目录**：`receipt.json` 必须放在 `.dispatch/runs/<run-id>/`，**不要**写进 worktree——写进 worktree 会被判 `write scope: out of scope: receipt.json`。
2. **land 前主仓必须干净**：`land` 只忽略 `.dispatch/`，`docs/`、`tickets/` 里的新文件都会让它报 `main checkout is dirty`，**verify 绿了不代表能 land**。落地前跑 `git status --porcelain`，只剩 `.dispatch/` 才动手。

## 执行端三条路

| 你有的 | 怎么走 |
|---|---|
| teammate（`list_agents` 里真有） | `handoff <id> --to <它>` → `send_message` |
| DSH 看板（票必须 L3+） | `dsh push --workspace <id>` → `dsh run` → `dsh outcome --mark-done --evidence` |
| 都没有 | 自己在 worktree 干，交付里写"主代理自执行" |

## 整波

```bash
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py land --wave            # 按拓扑序逐票落地
```

## 纪律

- **一票一停**：别把整波塞进一个上下文（实测 10 票会 prompt_too_long）
- 失败先 `retry <id> --reason …`，不要手改 `.dispatch/state.json`
- 卡住：`doctor` → `doctor --fix` → `release <id>` → `sweep`