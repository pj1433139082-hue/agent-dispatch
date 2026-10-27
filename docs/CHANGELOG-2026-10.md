# CHANGELOG · 2026-10（agent-dispatch 0.1 → 1.7.2）

> 这份文件把 161 个提交（130 个版本号）压成一条主线，给接手的人看"为什么长这样"。
> 逐条历史看 `git log`；每条设计取舍看 `docs/adr/`。

## 一句话

把"派单"从口头约定变成**文件契约 + 可执行门禁 + 可核查证据**：谁做、在哪做、能写哪、拿什么证据、谁验收、怎么落地、怎么收口。

| 指标 | 数值 |
|---|---|
| 时间跨度 | 2026-10-21 → 2026-10-27（5 个工作日） |
| 提交 / 版本 | 161 / 130（v0.1 → v1.7.2） |
| 测试 | 117 个测试文件，`-j 8` 约 180s 全绿 |
| 第三方依赖 | **0**（纯 stdlib Python） |
| 命令行 | 40 个顶层命令 |

## 五个阶段

### ① 10-21 · 骨架（v0.1 → v0.2）
票据解析、lint、plan、render（一票一 worktree）、verify、review、land。
**核心取舍**：执行者只写 worktree 和运行目录，**不能改票据状态**——状态只能由 verify/review 推进。

### ② 10-22 · 编排协议（v0.7 – v0.11）
S1–S5 流水线（align → select → sign → spec → confirm → tickets）、`auto --protocol full`（context 注入 / brief 门 / checkpoint / closeout）、三视角取证（oss-scout / search-scout / adversary）。
**教训**：`auto` 在 5.4M token 上下文里跑到第 10 张票直接 `prompt_too_long` → 定下"一票一停"。

### ③ 10-23 – 10-24 · 证据与门禁（v0.20 – v0.72）
brief 两阶段（先只读、审批后才动手）、review-packet 冻结证据、L2+ 必须回填 `packet_hash`、L4 必须 `--human`、三道身份门（名字 / 自审 / 读包证明）。
**教训**：`--agent` 只是标签；**名字不等于执行者**。

### ④ 10-25 – 10-26 · 真会话倒逼（v0.73 – v0.99）
三个真实会话各暴露一类问题，直接变成功能：

| 会话 | 现象 | 产物 |
|---|---|---|
| `session-3db50841`（quote-cost） | 19 张票全 done，只有 8 个 run 落地；31 个 `dispatch/*` 分支、24 个 worktree 残留 | `wrap`（收口一条命令）、done ≠ landed、`.scratch` 不算主仓脏、`gc` |
| `session-8516e665`（ts-sweep-server） | 票面 Verify 要 ssh，沙箱跑不了，重试两次无用 | ADR-0012 四条判据规则 + 重复失败提示 |
| `session-9a22e04f`（aquaops） | 6 个 persona 各自并行，但 `assign --persona` 一次没调、状态仓在子目录根上看不见 | `new --persona`、`roots`、`status --all` |

同期落地：**八个职能队友**（ADR-0013）、`maxMembers` 8→16、`dsh-agent-team-roster` 安装文档（Windows 解 asar）。

### ⑤ 10-27 · 四条流程实战 + 同步（v1.0 – v1.7.2）
把 A/B/C/D 四条流程各在真仓库跑一遍，用发现的问题继续收口（见下）。

## 五条能力主线

| 主线 | 一句话 | 关键命令 |
|---|---|---|
| 票据契约 | 一张票一个 Markdown，写域/判据/验收项强制 | `new` `lint` `plan` |
| 证据链 | brief → render → receipt → verify → packet → review → land，每步留文件 | `brief` `verify` `review-packet` `review` |
| 门禁 | L2+ 人格门、brief 质量门、S3 空壳门、判据强度（`weak_verify`） | `render` `confirm` `lint` |
| 落地 | 一票一分支 / `--append` 累积 / `--verify` 合后复跑 | `land` `land --wave` |
| 运维 | 体检、收口、回收、重建索引 | `doctor` `wrap` `gc` `repair` `sweep` |

## 四条流程实战（2026-10-27）

| 流程 | 怎么跑 | 抓到的真问题（已修） |
|---|---|---|
| **A** 需求→票 | align → select → sign → spec → confirm → tickets | `confirm` 当时**接受空壳 spec**；确认后改 spec 不算数 → 加七节检查 + `spec_sha256` |
| **B** 单票执行 | brief → render → executor 队友 → verify → reviewer 队友 → land | 第一次 verify 撞 `.gitignore` 未提交（每个新项目都会）；reviewer 抓到 5 条，其中 `context.md` 谎报 "first run" |
| **C** 批量 | `auto` + `land --wave` + `--append` + `--verify` | wave 落出 N 条互不包含的分支 → `--append` 累积；合后不验 → `--verify` |
| **D** 运维 | 造 4 种病 → doctor/wrap → 恢复 | `doctor --fix` 清不掉超期 run；执行器脚本用 worktree 旧快照导致 `receipt.json is missing` |

## 三次"看起来绿其实是假的"

1. **假测试**（verifier 队友发现）：`test_wave_continue_on_error` 的失败票排在最后，`break` 和 `continue` 输出同形 → 改写成"失败票在前 + 不带 flag 时后面的票不许落"。
2. **假文档改动**（自己踩）：两次用字符串替换改 `test-plan.md`，锚点在文件里不存在 → `replace` 静默无效，提交只带了版本号。现在有 `tests/test_docs_sections.py` 钉住关键小节。
3. **假绿**（CI 发现）：本地 117 个测试全绿，第一次 CI 就红——`D:/x` 在 Windows 是绝对路径、在 Linux 是相对路径。**本地绿不等于绿**。

## 文档索引

| 想知道什么 | 看哪 |
|---|---|
| 每个决策为什么这么定 | `docs/adr/`（0001–0013） |
| 术语（判据/验收项/执行根/落地区间…） | `GLOSSARY.md` |
| 命令全表（自动生成） | `docs/commands.md` |
| 四条流程谁产出谁消费 | `docs/flows.md` |
| 测试计划、覆盖矩阵、每轮协议 | `docs/testing/test-plan.md` |
| 八个职能队友与派活模板 | `docs/team/README.md` |
| 团队名额与删成员（Windows 实操） | `docs/team/roster-setup.md` |

## 明确没做

- `land` 之后的"在累积分支跑全量 Verify"只做到"逐票命令去重跑一次"，不是整套回归。
- 没有集成者角色：多条 land 分支仍需人工 merge 或 `--append` 累积。
- 跨平台只在 Windows（开发）与 ubuntu-latest（CI）两处验证，macOS 未跑过。
- 判据强度的唯一硬证据仍是"把实现改坏它会红"（变异检查），没有自动化门禁。
