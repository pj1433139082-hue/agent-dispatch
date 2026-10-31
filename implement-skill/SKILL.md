---
name: implement-dispatch
description: 按票执行：brief 审批 → render（一票一 worktree）→ 执行端动手 → verify 独立验收 → review 异体评审 → land 到 integration branch。触发：implement-dispatch、按票开发、派单执行、跑票、验收落地。
---

# 4/4 · Implement

> **done ≠ landed**：`review` 通过只是"票做完了"，代码还在 **worktree 分支**（`dispatch/<run-id>`）上，主分支和 integration branch 都没有它。
> 要进 integration branch 必须跑 `land <id>`（只建分支、不 push、不合并 main）。
> `status` 会给"done 但没落地"的票标 `-> 未落地（dispatch land <id>）`；`dispatch wrap` 会报 `N ended run(s) without landing.json`。

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
- `note` 可以**和可复算证据混用**（file/inline/command 都在时不会 degraded）；只有"**仅 note**"才降级
- 完整 schema 在 `references/ticket-contract.md`，每次 `render` 也会写进 `work-order.md` 的 `## Receipt contract`

## brief 里的方案备选（Design It Twice 轻量版）

**触发**：Risk ≥ L3、或接口拿不准、或 Write scope 跨 ≥2 个模块。其余小票不用写。

写两节：

- **方案 A**：一句话 + 关键取舍（复杂度 / 改动面 / 风险）
- **方案 B**：必须和 A **结构上不同**（不是改个名字）
- **推荐哪个、为什么**；被否的那个一句话说明为什么不选

L4 或"新建模块/接口"时，升级为并行子代理各出一版（用 codebase-design 的 Design It Twice），再把对比写回 brief。**只写一个方案不算过**——批准人看不到取舍就没法批。
## brief 的判据

`dispatch brief <id> --check` 只校验"五段非空、不是占位"（`<填写：…>`），**不判长度和内容质量**；写没写清楚由批准的人负责。

## 落地前后的小事

- **"先提交"提到哪**：直接 commit 到 `main`（land 只建分支、不动 main）。
- **验收报告不用提交**：land 之后写报告会让 main 变脏，留着未跟踪即可。
- **父票 vs 历史票**：本轮任务的父票和各轮遗留票的写域冲突一样处理——不改它、串行跑新票。

## 两条硬规矩（实测踩过）

1. **回执写 run 目录**：`receipt.json` 必须放在 `.dispatch/runs/<run-id>/`，**不要**写进 worktree——写进 worktree 会被判 `write scope: out of scope: receipt.json`。
2. **land 前主仓必须干净**：`land` 只忽略 `.dispatch/`，`docs/`、`tickets/` 里的新文件都会让它报 `main checkout is dirty`，**verify 绿了不代表能 land**。落地前跑 `git status --porcelain`，只剩 `.dispatch/` 才动手。

## 执行端三条路

| 你有的 | 怎么走 |
|---|---|
| teammate（`list_agents` 里真有） | `handoff <id> --to <它>` → `send_message` |
| DSH 看板（票必须 L3+） | `dsh push --workspace <id>` → `dsh run` → `dsh outcome --mark-done --evidence` |
| 都没有 | 自己在 worktree 干，交付里写"主代理自执行" |

## land --wave 的语义（实测）

- **每票一条 integration 分支**，都基于同一个 target；**不是**一条合并分支。PR 要按票开。
- 依赖顺序只决定**建分支的顺序**，不会把上游改动带进下游分支——下游分支里看不到上游文件，别指望"落完 wave 就有完整功能"。
- 完成判定是 **state=done 或 票面 `Status: done`**（两者 OR）；票面写着 ready 但 state done 的票也会被落。
- `--require-closeout` 现在对 wave 也生效（closeout 不是 pass 的票会被判 FAILED）；`--require-packet` / `--require-attestation` 仍只作用于单票 `land`。
- wave 会先 lint 全部票：任何 lint error 直接退出，一张都不落。

## 整波

```bash
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py land --wave            # 按拓扑序逐票落地
```

## retry 的三件事（实测）

1. `retry` 不只救 `failed`：**卡在 `claimed` 的 run 也能 retry**（直接到 running，attempt+1）。
2. **receipt 和 evidence 不会归档**：旧 `receipt.json` 还在 run 目录里，执行端必须为新的 attempt 重写，否则 verify 会复算旧证据。
3. 归档的只有 `attempts/verify-01.json`、`review`、`closeout` 的快照；`logs/01.log` 会被覆盖。

## 收口闭环（照这个顺序走）

```
wrap                     # 1. 发现问题：failed / 超期 / 未落地 run / 会挡 land 的脏文件
land --wave --dry-run    # 2. 看清会落哪几张（WOULD / SKIP），不建分支
land --wave              # 3. 真落（或逐张 land）；dirty 的先提交
wrap                     # 4. 复验，exit 0 才算收工
```

## 批量落地前先预览

```bash
dispatch land --wave --dry-run     # WOULD / SKIP，不建分支
dispatch land --wave               # 确认后再落
```

## 会话收口（每次收工前一条命令）

```bash
python C:\Users\14331\.agents\skills\agent-dispatch\scripts\dispatch.py wrap        # 状态计数 + doctor 全部问题 + 下一步动作；干净 exit 0，有事 exit 1
```

- 它会直接告诉你：`dispatch retry 03`、`dispatch sweep`、`git add/commit 或 .gitignore 掉 …`
- **回来时**同一个命令也能用：exit 1 就还没收干净
- 一次会话别超过 3–5 张票（ADR-0010 的实测来源：10 张 → 5.4M tokens → prompt_too_long）

## 三条硬纪律（都来自真实会话）

1. **render 之后不要改票**：改一个字 `verify` 就报 `ticket changed after render`；要改就 `retry` 或重新 `render`。
2. **receipt.criteria 必须正好 1..N**（N = 票面 Acceptance 条数）：多一条少一条都判失败。
3. **说"auto 模式"就用 `dispatch auto`**：不要用人工 brief/render 冒充自动推进；`auto` 会写 `auto.json`、checkpoint、feedback，人工跑是没有这些的。

## 纪律

- **一票一停**：别把整波塞进一个上下文（实测 10 票会 prompt_too_long）
- 失败先 `retry <id> --reason …`，不要手改 `.dispatch/state.json`
- 卡住：`doctor` → `doctor --fix` → `release <id>` → `sweep`