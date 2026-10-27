---
name: setup-agent-dispatch
description: 给一个仓库做一次性 dispatch 配置（票目录、执行端模式、默认评审人、AGENTS.md 入口、健康基线），之后 agent-dispatch 的所有命令都按这份配置工作。触发：初始化 dispatch、给项目接 dispatch、dispatch setup、配票目录、配执行端。
---

# Setup agent-dispatch

一次性把"这个仓库怎么用 dispatch"定下来，写进 `.dispatch/config.json`，其它命令都读它。
**不是脚本，是对话**：先探、再问、再写、最后体检。

## 1. 探（不要假设）

- `git status` / `git remote -v`：是不是 git 仓库？（不是就提醒：dispatch 的 verify 依赖 git）
- 票在哪：`tickets/`、`.scratch/*/issues/`、还是别处？
- 有没有 `.dispatch/config.json`（跑过 setup 没有）
- `AGENTS.md` / `CLAUDE.md` 有没有 `## Agent skills` 段
- CI：`.github/workflows/` 里有没有跑 `pytest` / `acceptance.py`
- 有没有历史 run：`.dispatch/runs/`（有就先 `dispatch doctor` 看健康度）

## 2. 问（一次一问，每问给推荐）

**A. 票目录**
> 推荐：仓库里已有的那个（`tickets/` 或 `.scratch/<feature>/issues/`）。没有就建议 `tickets/`。

**B. 执行端模式**
> - `teammate` —— 派给 harness 里的 teammate（需要 `list_agents` 里真有目标）
> - `dsh` —— 推到 DSH 看板，人在板上点 run
> - `command` —— `auto --executor "<cmd>"`（没有 teammate 时等于主代理自执行）
>
> 推荐：看会话里 `list_agents` 有什么；只有 lead 就选 `command` 或 `dsh`，别选 teammate。

**C. 默认评审人**
> 推荐：一个**不是执行者**的名字（异体评审）。可以留空，之后每票用 `--reviewer` 指定。

## 3. 写

`@bash
python ~/.agents/skills/agent-dispatch/scripts/dispatch.py setup \
  --tickets tickets \
  --executor-mode teammate \
  --default-reviewer reviewer-b
`@

它会写 `.dispatch/config.json`（幂等：重跑不带参数就保留原值）。

## 4. 接进入口（可选但推荐）

在 `AGENTS.md`（没有就 `CLAUDE.md`）加一段：

`@markdown
## Agent skills

### agent-dispatch

票据在 `<tickets_dir>/`，派单走 `agent-dispatch` 技能；执行前先 `dispatch brief`，验收用 `dispatch verify`，评审用 `dispatch review --reviewer <非执行者>`。
`@

## 5. 收尾

`@bash
python ~/.agents/skills/agent-dispatch/scripts/dispatch.py doctor
`@

- `OK` → 告诉用户"配好了，这些命令现在会读这份配置：lint / plan / render / auto / status / doctor / handoff"
- 有 issue → 先修（`doctor --fix` / `retry@ / `release`），再报完成

## 边界

- 只写 `.dispatch/config.json` 和 `AGENTS.md` 那一段；不动票、不动 src、不动 CI（CI 要加拉一条 `acceptance.py`，问过再加）。
- 不要替用户决定执行端；`list_agents` 里没有的名字不要写进配置。
