# agent-dispatch 测试计划（v1）

> 目标：不要"我说它能用"，要"别人拿文档就能跑通，且门真的会拦"。
> 方法：每轮**开一个全新的 DSH 会话**（任务看板卡片，票必须是 L3+，否则板上跑不了命令），只给它技能文档 + 一句任务，让它自己走；它踩到的每个坑都要落到**代码或文档**上，再跑下一轮回归。

## Problem Statement

技能的正确性目前靠作者自己跑命令来证明。这有两个问题：作者知道所有隐含前提（该先 brief、回执写哪、land 前要提交），所以测不出"文档没说"的坑；而且同一上下文里越跑越顺，掩盖了冷启动要面对的现实。

## Solution

用**任务看板起新会话**做黑盒验收：每轮一个独立会话、一个独立仓库状态、一份必须交回的报告。报告里的"文档没说但我必须猜"就是缺陷清单；修完再跑下一轮，直到连续两轮不再出现新的"必须猜"。

## 测试对象与接缝

- **接缝只有一条**：命令行入口 `scripts/dispatch.py`（黑盒），外加它写的文件（`.dispatch/`、`docs/`、`tickets/`、worktree）。
- 不测内部函数；单元测试只用于把已发现的坑**钉住**（每个坑一条回归测试）。
- 每轮跑完必须能用一个命令复现：`python -m pytest -q`。

## 覆盖矩阵（命令 × 路径）

> v0.98 更新：上轮列出的 6 条真空白已全部补上测试（`tests/test_gap_*.py`，6 例）。补测过程中发现并修了一个真 bug：`sign --reject` 之后 `spec` 仍能通过（打勾判定把"☑ 打回"也算成已批准）。

| 区域 | 已覆盖（有测试） | 真实空白（无测试） |
|---|---|---|
| S1–S5 主链 | align / select / questions / **sign 三态（pass / hold / reject）** / spec --force / stage --prompt / confirm / tickets / lint / plan | — |
| 单票执行 | brief / render（含 `--no-worktree`）/ start / verify / review（含 `--accept-degraded`、L2+ 哈希、L1 自审、**L4 拒绝路径**）/ land | — |
| 自动推进 | auto 默认 / `--protocol full` / `--max-attempts` / attempt 用尽 / `--resume` / **`--until land` 时 closeout 不过** | — |
| 波次落地 | `land --wave` / 依赖顺序 / `--require-closeout` / 混入 closeout 不过的票 / `--dry-run` / **`--continue-on-error`** | — |
| 证据与收口 | verify 判据 / closeout 五条 / criteria 条数不匹配 / note-only→degraded→accept / checkpoint | — |
| 运维 | doctor/`--fix` / claim/release / sweep / repair（含 evidence_mismatch）/ seat / roots / **`gc` 对未 land worktree 判 HOLD** | — |
| 人设/导出 | personas / assign / new --persona / context / export 四格式 | — |
| 看板 | push / status / run / outcome / update / archive / mark-done 缺证据拒付 / **push 对 L3 以下票的警告** | — |
## D 路径演练记录（2026-10-27，dispatch-a-smoke）

故意造脏：1 张 failed 票、1 个超期 claimed run（带租约）、1 张 done 未落地、主仓脏文件。

| 步骤 | 结果 |
|---|---|
| `wrap` | exit 1，报 3 类问题 + Next 四步 |
| `doctor` | `failed 10` / `deadline 1 overdue` / `leases 1 active` / `checkout scratch-note.txt` |
| `sweep --json` | `over_deadline: true, age_seconds: 80, deadline_seconds: 60` |
| `doctor --fix` | **清不掉超期 run**（文档已写），`auto` preflight 仍报 `runs past their deadline: 11` |
| `auto --resume` | 必须加 `--force` 才能跳过全局 preflight |
| 恢复 | `release 11` → `retry 10/11` → `auto --resume --force` → `review` → `land --wave --branch wave/drill --append --verify` |
| 收口 | `gc`（预览 12 条 REMOVE）、`doctor` OK、`wrap` **CLEAN / done 12** |

**演练抓到的真问题（v1.6.1 修）**：`auto --executor "python tools/exec_x.py"` 用的是 **run worktree 里的旧快照**——脚本在 render 之后才提交，worktree 里没有它/是旧版 → 执行器静默失败 → 只看到 `receipt.json is missing`。现在这条报错会直接说清：脚本必须在 render **之前**提交，或改用绝对路径。

## 文档改动必须由 fresh 会话复现（v1.0.2）

改 `SKILL.md` / `docs/**` / 模板后，让一个**没有当前上下文**的执行者（`spawn_teammate({context:"fresh"})` 或看板新会话）照文档做一遍，报告必须含：

1. 逐条判定表（步骤 | 现实是否吻合 | 证据）
2. "外行会卡在哪"清单（≤5 条）
3. 一句话结论：可直接照做 / 需要补 X

**依据**：2026-10-26 的 `roster-setup.md` 复现审查抓出 4 条硬错（体积口径 158MB 实为 174/401/243MB；`patchReload` 键在 0.2.1-rc.3 不存在；`list_agents` 计数含 lead 导致门槛差一档；web profile 没装 Agent Teams 写进去静默无效）+ 4 个遗漏（回滚留毒、删除会中断运行中回合、`cleanup_team` 判据是"回合不在跑"、缺校验口径）。作者自己读三遍看不出来。

## 跑全量期间不要改仓库（v0.99.5）

- 实测：`-j 8` 跑到一半时改了 `pyproject.toml` / `__init__.py` 的版本号，`test_skill.py` 里"构建副本 → 比对 `__version__`"的两条断言当场变红，看起来像并发 bug，实际是**测试中途改了源**。
- 纪律：跑全量期间只读；要改代码就等它跑完。
- 并发实测（同机、107 文件、稳定树）：`-j 4` ≈ 295s，`-j 8` ≈ 180s；8 路时最后一批是长尾，再加收益递减。

## 每轮协议（固定动作）

1. 建一张 **L3** 任务票 → `dsh push --workspace <id>` → `dsh run`。
2. 卡片 prompt 只给：技能路径、目标功能（一个 slug）、"每步记录命令/退出码/关键输出"、"报告写到 REPORT-LOOPn.md"、"文档没说但我必须猜的清单"。
3. 轮询到 `done`，读报告，按"影响流程"排序，**只修前 3 条**（避免一轮改太多）。
4. 每条坑：能写测试的写测试（红→绿），纯文档的改 SKILL。
5. 提交 + 安装（`build_skill.py` + 逐文件复制），跑全量测试 4 批。
6. 下一轮复验上一轮的 3 条，确认"能照文档做"。

## 验收标准（这个计划本身算完成的条件）

- [ ] 连续两轮报告里"文档没说但我必须猜"为空
- [ ] 所有门都被**真实失败**打过一次：问卷未填、S2 未签、S3 未 confirm、brief 未批、verify failed、review 同名人、L2+ 缺 packet_hash、land 脏检出、wave 的 closeout 门、`--require-attestation`
- [ ] 每条坑都有对应回归测试或 SKILL 明文
- [ ] 全量测试绿，`doctor` 在示例仓库 OK

## User Stories

1. 作为技能维护者，我想让一个**没读过源码**的会话按文档跑通全链，这样我才知道文档够不够。
2. 作为技能维护者，我想让新会话把"必须猜"的地方写下来，这样我不靠猜去补文档。
3. 作为派单员，我想让每道门在**不该过的时候真的过不去**，这样"完成"不是我说了算。
4. 作为派单员，我想在 `land --wave` 里看到哪张票被 closeout 拦下，这样不会把半成品落进分支。
5. 作为执行者，我想知道回执写哪、写什么形状，这样 verify 不会因为我放错目录就判失败。
6. 作为执行者，我想知道 `retry` 之后 receipt 要不要重写，这样第二次验收不会复算旧证据。
7. 作为评审者，我想知道 L1/L2+ 分别要什么证明，这样我不会在 L1 上传了哈希却被静默忽略。
8. 作为运维，我想知道 `gc --apply` 会删什么，这样我不会误删还要用的分支。
9. 作为运维，我想知道 `auto` 的 preflight 为什么被别的票挡住，这样我不会以为是自己的票有问题。
10. 作为读者，我想在 SKILL 里直接看到"哪些是实测过的边界"，这样我不用读完源码才敢用。

## Implementation Decisions

- 测试只走 CLI（黑盒），每个坑先写回归测试再改实现。
- 新会话一律通过**任务看板**起，票必须 L3，否则板上会话无法执行命令（workspace-write 会 EPERM）。
- 每轮最多修 3 条，按"影响流程"排序，避免一次改动面过大。
- 修完必须重新打包安装，否则下一轮还在测旧版本。
- 报告文件不提交（land 后写，留未跟踪），避免把 main 弄脏。
- 覆盖矩阵是唯一进度看板；新增区域先加到矩阵再开轮。

## Testing Decisions

- 好测试：从 CLI 进去、断言**可观察行为**（退出码、stdout/stderr 关键字、生成的文件内容），不断言内部函数调用。
- 回归测试放在 `tests/`，命名按坑起（如 `test_lease_renew.py`、`test_attestation_gate.py`）。
- 已有先例：`test_claim_concurrency.py`（并发）、`test_land_wave.py`（波次）、`test_review_identity.py`（身份门）。
- 每轮结束跑四批测试（`pytest -q` 分四份文件列表），避免单次超时。

## 决定：不为 wrap 单设 CI job

- 决定：不新增独立的 wrap job。
- 理由：本仓库自身没有 .dispatch/ 票，单独跑 wrap 永远 CLEAN，等于空转；真正的价值在"跑完真实链路之后"——那一步已经进了 acceptance 的 A 路径（wrap_exit == 0 且 issues == []）。
- 重议条件：如果本仓库自己开始用 ticket 流程，再加独立 job，并用 paths 过滤只在 .dispatch/** 变化时触发。

## Out of Scope

- 不做性能/压力测试（除了 claim 并发那条）。
- 不测 DSH 看板本身的实现，只测 dispatch 与它的接口。
- 不覆盖 Windows 之外的平台（当前只用 Windows 的 cmd.exe 语义）。
- 不做安全渗透（写域逃逸只测 symlink/junction 一条）。

## Further Notes

- 十轮实测已修：closeout 的"声明却没改"、wave 的 closeout 门、lease 续租、release no-op、land 的 `--require-attestation`、context 自引用、checkpoint 未跟踪文件。
- 下一轮建议先打**波次里混一条 closeout 不过的票**，那是唯一还没被真实失败打过的门。
