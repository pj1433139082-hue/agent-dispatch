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

| 区域 | 已覆盖 | 待覆盖（本计划重点） |
|---|---|---|
| S1–S5 主链 | align/select/questions/sign/spec/confirm/tickets/lint/plan | `sign --reject`、`stage --prompt` 的 JSON 形状、`spec --force` |
| 单票执行 | brief/render/start/verify/review/land | `review --accept-degraded`、L4 的 `--human` 门、`--no-worktree` 逃生口 |
| 自动推进 | auto 默认、`--protocol full`、`--max-attempts` | **attempt 用尽**后的状态、`--until land` 时 closeout 不过的表现 |
| 波次落地 | `land --wave`、依赖顺序、`--require-closeout` | **混入一条 closeout 不过的票**（整波停还是跳过）、`--continue-on-error` |
| 证据与收口 | verify 判据、closeout 五条、checkpoint | closeout 的 **criteria 条数不匹配**、`note-only` → degraded → `review --accept-degraded` 全链 |
| 运维 | doctor/`--fix`、claim/release、sweep、repair、gc、seat | `repair --write` 在 evidence_mismatch 下的行为、`gc --apply` 对"未 land 但有改动"的处理 |
| 人设/导出 | personas/assign/context/export 四格式 | `export` 对 **blocked 票**是否过滤、`assign` 的 persona 文件丢失时的报错 |
| 看板 | push/status/run/outcome/update/archive | `dsh outcome --mark-done` 缺证据时的拒付（已测）、`dsh push` 对 L1 的警告（已测） |

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

## Out of Scope

- 不做性能/压力测试（除了 claim 并发那条）。
- 不测 DSH 看板本身的实现，只测 dispatch 与它的接口。
- 不覆盖 Windows 之外的平台（当前只用 Windows 的 cmd.exe 语义）。
- 不做安全渗透（写域逃逸只测 symlink/junction 一条）。

## Further Notes

- 十轮实测已修：closeout 的"声明却没改"、wave 的 closeout 门、lease 续租、release no-op、land 的 `--require-attestation`、context 自引用、checkpoint 未跟踪文件。
- 下一轮建议先打**波次里混一条 closeout 不过的票**，那是唯一还没被真实失败打过的门。
