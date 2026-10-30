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

## 2026-10-30 · v1.10.0：评审窗口、变异检查、集成者

- `review-window <slug> --open/--close`：选型包证据 sha256 快照；评审后改动 → exit 1；team 模式签字前必须有干净窗口。
- `mutate <id>`：退回 `base_commit` 重跑票面 Verify，全过 = `weak`（exit 1），至少一条失败 = `killed`（exit 0）。
- `integrate --branch X --from a --from b [--verify-all]`：多分支按序集成，合后可选全量回归，记录进 `integrations.jsonl`。
- CI：test job 加 `macos-latest` 矩阵。
- 测试：`tests/test_ops_commands.py`（5 条）；ADR 0016。

## 2026-10-30 · v1.9.2：证据矛盾门

- `sign` 在 `03-adversary.md` 的结论行写着"证据不足"时拒绝 `pass`（除非 `--note` 写明要补的证据）；`--hold` 不受影响。
- 模板 brief 里的"结论三态"说明不触发（只在非模板文件里认结论行）。
- 测试：`tests/test_sign_adversary_contradiction.py`（4 条）。

## 2026-10-30 · v1.9.1：grill team 验收反馈

- 交叉评审轮明确**只读**：任何人（包括自己那份）不许改文件；要改由 Lead 汇总后另开一轮。
- 签字口径：adversary 判"证据不足"而 01/02 建议采用时，默认签 `--hold` 并写明待补证据，不签 `pass`。
- 技能统一用完整 `python <技能目录>/scripts/dispatch.py` 调用（`dispatch` 不一定在 PATH 上）。

## 2026-10-30 · v1.9.0：grill 三会话并行（team 模式）

- `select --mode team`：证据包标记为"每份证据由独立子会话产出"；`--mode solo`（默认）保持旧行为。
- `sign` 在 team 模式下要求每份证据带 `Persona: <角色 persona>` 行、且不再是 `## What to produce` 模板，否则拒绝签字。
- `grill-dispatch` 技能新增「三会话并行」：spawn 三个 fresh teammate（角色卡 + 信息源隔离 + 只写自己文件）、回收格式、交叉评审 `06-cross-review.md`、无 teammate 时的 solo 降级留痕。
- 测试：`tests/test_select_team_mode.py`（4 条）。
- ADR 0015。

## 2026-10-30 · v1.8.4：人格验收反馈补齐

- 回执 persona 现在**同时比对 source 与 sha256**（此前只比 sha，source 写错也能过）。
- `persona_required` 在 render 时冻结进 run：verify 不再重读 config，render 后改 `persona_policy` 不会改变这张 run 的判定。
- 工单的回执契约里写明 persona 字段（顶层 `{"persona": {"source","sha256"}}`），不再只靠 ADR。
- `status` 对 `review` 状态的 run 显示 `degraded 验收（review 需 --accept-degraded）`。
- 测试：`tests/test_persona_binding.py` 增至 9 条（新增 source 不匹配、required 冻结）。

## 2026-10-30 · v1.8.3：人格绑定与审计（ADR 0014）

- `render` 把角色卡的 `sha256` / 来源 / 名字写进 `run.json.persona`；票面 `Persona:` 只算意图。
- `persona_policy=off` 或新 flag `--allow-unassigned-persona` 会在 run 里记 `persona_waiver`（来源 + 时间），不再静默关闭。
- `verify` 新增 persona 审计：角色卡被改、L2+ 新 run 回执缺 `persona`、回执与绑定不一致 → degraded（不 failed）。
- `status` 显示 `persona <名字>` / `persona waived (<来源>)`；`wrap` 只对"该绑没绑且无豁免"的未落地 run 报 issue。
- v1.8.2 及以前的 run 视为 legacy，不追溯。
- 测试：`tests/test_persona_binding.py`（7 条）。

## 2026-10-29 · v1.8.2：三处门禁谓词修正（TDD 红→绿演练产出）

- **verify**：degraded 判定从"证据前缀全 attested"改成"整条 criterion 全部 attested"——证据书写顺序不再改变结论（note 写在 file 前面不再误判降级）。
- **land --wave --require-attestation**：补上单票已有的 packet 核验；此前该 flag 在波次路径是静默 no-op。
- **review --verdict fail**：degraded 验收可以被驳回（`--accept-degraded` 只约束放行），票回到 `failed` 可 `retry`，不再永久钉在 `review`。
- 回归用例：`tests/test_verify_mixed_note_evidence.py` / `test_land_wave_attestation.py` / `test_review_reject_degraded.py`（均为"先红后绿"产出）。
- **land --wave 补 review-packet 门**：波次路径此前完全不检查 `review-packet.md`（单票默认要求），现在默认同样要求，`--no-require-packet` 可跳过（老 run 迁移用）。
- **检查去重**：`--require-attestation` 的判定抽成 `_attestation_problem()`，单票 `_cmd_land` 里重复写两遍的块合并成一处。
- **补零覆盖用例**：`tests/test_verify_allow_main_drift.py`（2 条）覆盖 `verify --allow-main-drift`——此前该 flag 零用例。
- **文档口径**：`absent` 证据明确"相对 Run 目录判存在"；`--accept-degraded` 的 help 说明只约束放行；degraded 判定注明"按整条 criterion、与证据顺序无关"。

## 2026-10-29 · v1.8.1：三个下游技能改成「原技能底座 + 差异层」

- `grill-dispatch` / `to-spec-dispatch` / `to-tickets-dispatch` 不再各自重写删减版：开头显式 `Skill("grilling" / "to-spec" / "to-tickets")`，正文只留 dispatch 产物与门禁，并写冲突裁定与「上游锚点」。
- 补齐被删掉的原技能协议：设计树/前沿/分轮追问/每题推荐答案；测试接缝并与人确认、User Stories 要长、Implementation Decisions 写法约束；tracer-bullet 垂直切片、预重构、宽改 expand–contract、拆完人审三问。
- 按 2026-10-29 看板无人值守实测（自评 20/24）修正文档与工具不一致：`sign` 实际改 4 行、`questions` 拒绝 exit 2、`select` 必写 `00-panel.json`、`--with` 多写 04/05、`tickets` 草稿在写域外、新票撞历史票写域的处理。

## 2026-10-29 · v1.8.0：land 之后的整分支全量回归

- 新增 `land --verify-all "<命令>"`（可重复，重复命令只跑一次）：落地后在 integration branch 的临时 worktree 里跑**你给的回归命令**；失败把 `landing.json` 记成 `landed-unverified`、`verify_all_status: fail`，退出码 1。
- `land --wave --branch X --append --verify-all` 只在整波落完之后跑一次；不带 `--branch` 在落地前报错。
- 与 `--verify` 的分工：`--verify` 复跑票面 Verify（这张票能不能跑），`--verify-all` 跑整套回归（这条分支还能不能用）。
- `--verify-all-timeout` 默认 1800 秒/条。

## 明确没做

- ~~`land` 之后的"在累积分支跑全量 Verify"只做到"逐票命令去重跑一次"，不是整套回归。~~ **v1.8.0 已补**：`--verify-all` 把整套回归接进 land；仍未自动推导"受影响目录"，回归命令要人给。
- 没有集成者角色：多条 land 分支仍需人工 merge 或 `--append` 累积。
- 跨平台只在 Windows（开发）与 ubuntu-latest（CI）两处验证，macOS 未跑过。
- 判据强度的唯一硬证据仍是"把实现改坏它会红"（变异检查），没有自动化门禁。
