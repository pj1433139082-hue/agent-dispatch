# Spec: security-audit-fixes

> 来源问卷：docs/questions/security-audit-fixes.md
> 取证：docs/selection/security-audit-fixes/（01-oss / 02-sources / 03-adversary / 06-cross-review）
> 审计原文：docs/verification/2026-11-02-security-audit-findings.md

## Problem Statement

2026-11-02 的安全审计（standard 档，源码级，本机无 OS 沙箱故三条均为 `needs_validation`）在 agent-dispatch 的**门禁层**找到三条真实旁路。它们的共同点不是"没有认证"（那是设计），而是**工具手里已经有可信证据，却没拿去比对**：

1. **F1 fallback 落地件不受内容约束**。`land` 的正常路径用 `diff_hash`（字节）绑定审查对象（`landing.py:66-86`），但 `--from-commit` 分支改用 `git diff --name-only` 的**路径集合**（`landing.py:89-104`），且同时短路了 worktree 存在（`:209`）与 run 分支存在（`:239`）两道门。同一仓库里审查与落地用了**两种强度的证据**。

2. **`repair` 能在无证据时把票提升到 `done`**。写回索引的 state 直接取自 `run.json` 的 state 字段本身（`lifecycle.py:188`），`evidence_state()` 只在返回非 `None` 时做交叉检查（`:203`）。因此"run.json 说 done + 一个证据文件都没有"→ 返回 `None` → 不计 mismatch → `--write` 直接抄 done。**不需要伪造任何证据**。另有两个未覆盖的同源出口：`dsh outcome --mark-done`（`cli.py:3210-3235`，只查 evidence 路径存在）与票面自述 `status: done`（`export.py:39-42`）。

3. **`command` 证据是自述即可通过**。`verify.py:331-350` 只校验形状与 `exit_code == expect_exit`，返回 `attested: False`；`degraded` 仅在"整个 criterion 全 attested"时置位（`:409`），故纯 command 回执得 `passed`，review 完全不需要 `--accept-degraded`。这与 `references/ticket-contract.md:79`「`passed`：所有 criterion 都有**可复算证据**」直接冲突。

**为什么现在必须修**：这个工具的全部安全价值就是这三道门。门可以被"证据缺失"和"自述证据"绕过时，`done` 这个状态就不再代表"验证过且异体评审过"，而依赖它解锁的下游（`export.py:20-21`、`graph.py` 波次）会连带失真。

**已知的文档自相矛盾（必须同批修，否则 spec 自相矛盾）**：
- C1：`SKILL.md:328`「这张票不写」 vs `:345`「只打印不拦」。
- C3：`ADR-0017:11` 记 `--from-commit`「被否」，`CHANGELOG:115` 记「已实现」，ADR 无 Status 字段。
- C4：`SKILL.md:666`「只有 note 算 attested」 vs `ticket-contract:79`「passed = 都有可复算证据」。

## Solution

让"票变成 `done`"这件事**只有一条路径**（证据派生），让"落地"这件事**只有一种内容口径**（字节哈希），让"判据"这件事**必须要有可复算物证**——并把由此失效的文档一次性对齐。

具体五件事：

- **D1**：删除 `land --from-commit` 整条路径。恢复出口已存在（`drop` / `gc` 归档，`lifecycle.py:142-174`），且成熟实现 gstack 有 review↔内容绑定但**没有**"从某个 commit 落地"的参数。
- **D2**：`repair` 禁止在无证据时升 `done`，**含索引里没有该行时的`added`新增路径**；写入记录记 `status_source`。
- **D3**：`command` 证据采用**替换语义**——command 不计入可复算证据，criterion 必须另有 `file`/`inline`/`absent`/`log_hash`。
- **D4**：收口 `export.py:39-42` 票面自述 `status: done` 的第三来源。
- **H**：`verify._run_command` 补与 executor 一致的 `DISPATCH_*` 环境，消除"对执行者通过、对门禁失败"。

## User Stories

1. 作为 dispatcher，我希望 `land` 无论走哪条路径都校验**同一个字节哈希**，这样"我审过的代码"和"我落的地"不会是两份东西。
2. 作为 dispatcher，我希望 `--from-commit` 不存在，这样我不会在不知情的情况下用一条弱绑定的应急路径落地。
3. 作为 dispatcher，我希望 `repair --write` 永远**不能**把一张没有 `review.json: pass` 的票变成 `done`，这样磁盘上的状态重建不会给攻击者开新门。
4. 作为 dispatcher，我希望"run.json 说 done 但没有任何证据文件"被当成**可疑**而不是**不适用**。
5. 作为 dispatcher，我希望 `repair` 的输出明确告诉我每张票的 done 是**从哪个证据派生的**（`status_source`），这样审计能追。
6. 作为 dispatcher，我希望 `repair --write` 在索引里**没有**该票时不会凭 `run.json` 单向新增一条 done。
7. 作为 reviewer，我希望一张只靠 `command` 自述满足验收的回执**不能**拿到 `passed`，这样我签字时看到的是可复算物证。
8. 作为 reviewer，我希望往回执里掺一条无关的 `evidence/anything.txt` **不能**绕过可复算性要求（替换语义，不是计数语义）。
9. 作为 executor，我希望写 `Verify` 命令时拿到的 `DISPATCH_*` 环境变量与我自己执行时**一致**，这样我的判据不会"我这儿绿、门禁那儿红"。
10. 作为维护者，我希望 `ADR-0017` 明确记录 `--from-commit` 的最终状态（Superseded），这样下一个读 ADR 的人不会以为它还该存在。
11. 作为维护者，我希望 `SKILL.md` 关于 `repair` 的 mismatch 行为只有**一种说法**，这样实现者不用猜。
12. 作为维护者，我希望 `SKILL.md` 关于哪些证据算 `attested` 的说法与 `ticket-contract` 的 `passed` 定义一致。

## Delivery standard

- [ ] `dispatch land --from-commit` 不再存在（CLI 不再接受该参数，传了报错） <!-- verify: python -m pytest -q tests/test_land_conflicts_and_from_commit.py -->
- [ ] `_assert_reviewed_commit` 已删除，落地只剩 `_assert_reviewed_worktree` 一条内容口径 <!-- verify: python -m pytest -q tests/test_land_conflicts_and_from_commit.py -->
- [ ] `repair --write` 遇到"run.json=done 且三种证据全缺"时**不写 done**，且该票不出现在 `added` <!-- verify: python -m pytest -q tests/test_cli_repair.py -->
- [ ] `repair --write` 遇到"索引里没有该票 + run.json=done + 无证据"时不新增该票 <!-- verify: python -m pytest -q tests/test_cli_repair.py -->
- [ ] `repair` 现有能力不回归：dry-run / 新增有证据的票 / run_id 冲突 exit 1 / mismatch 跳过 <!-- verify: python -m pytest -q tests/test_cli_repair.py tests/test_repair_partial.py -->
- [ ] 每条 repair 写回的票记录 `status_source`（值域含 `evidence` / `run.json`） <!-- verify: python -m pytest -q tests/test_cli_repair.py -->
- [ ] 纯 `command` 证据的 criterion 不再能单独构成可复算证据（替换语义） <!-- verify: python -m pytest -q tests/test_verify_expect_exit.py -->
- [ ] `command` + 无关 `file` 证据的 criterion 仍判定为非可复算（挡住掺沙） <!-- verify: python -m pytest -q tests/test_verify_expect_exit.py -->
- [ ] 既有混合证据契约不回归：file/inline/absent/command/note 混用仍得 `passed` <!-- verify: python -m pytest -q tests/test_cli_worktree.py tests/test_verify_mixed_note_evidence.py -->
- [ ] 票面自述 `status: done`（无 run / 无索引行）不再解锁下游 <!-- verify: python -m pytest -q tests/test_export.py -->
- [ ] `verify` 子进程拿到与 executor 一致的 `DISPATCH_*` 变量 <!-- verify: python -m pytest -q tests/test_verify.py -->
- [ ] `ADR-0017` 含 `--from-commit` 的最终状态记录 <!-- verify: python -m pytest -q tests/test_docs_sections.py -->
- [ ] `SKILL.md` 关于 repair mismatch 只有一种说法 <!-- verify: python -m pytest -q tests/test_docs_sections.py -->
- [ ] `SKILL.md` 的 attested 口径与 `ticket-contract` 的 passed 定义一致 <!-- verify: python -m pytest -q tests/test_docs_consistency.py -->
- [ ] 全量测试通过 <!-- verify: python -m pytest -q -->
- [ ] 端到端验收通过 <!-- verify: python scripts/acceptance.py -->
- [ ] 人工核对：`docs/commands.md` 与 CLI 速查一致（`test_docs_consistency` 双向校验）

## Implementation Decisions

### D1：删除 `--from-commit`（不做"补哈希"）

**为什么删而不是补哈希（理由经第四条交叉评审修正）**

> ⚠️ 初版写的是「补哈希无效」。经第四条交叉评审核实 gstack 源码后**该理由被推翻**：从 commit 对象算内容指纹**技术上完全可行**——gstack `lib/evidence-bundle.ts:132-133` 用 `rev-parse HEAD^{tree}`、`lib/gate-diff/git.ts:223-229` 用 `git diff <parent> <sha>` 直接从 commit 产 diff，**都不需要工作树**。删的真正理由是**不值得**，不是做不到。

1. **两种口径**：两条路径核的不是同一个对象（路径集合 vs 字节哈希）。补就得新增第二种 diff 口径，违反 `ADR-0011 D1`「哈希只有一个定义」——要么改 ADR，要么改实现。
2. **实现成本**：`verify.py:97-98` 的 `_git` 写死 cwd、无 env 参数；指向临时索引必须改签名或注入 `GIT_INDEX_FILE`。
3. **使用场景已有出口**：该路径存在的唯一理由是「worktree 被毁」，而 `drop` / `gc` 归档（`lifecycle.py:142-174`）已覆盖。
4. **成熟实现不提供**：gstack 有完整的 review↔内容绑定，但**没有**「从某个 commit 落地」的参数——它只认内容指纹相等。

> **给下一个修法者的警示**：`landing.py:90` 的 docstring 自述「用文件清单核对」，与同文件 `:83-86` 核哈希的实现**不一致**。这个 docstring 会诱导人把 `--from-commit` 改成「只核文件名 + 要求 packet 存在」——**那才是真正的空签名**。删除本条路径时一并修掉这个 docstring。
>
> 另一条本次未采纳但值得记录的加固：`land` 的 `--require-attestation` **默认 False**（`cli.py:438-444`）。「评审对象可信」这件事 CLI 有能力表达，只是默认没打开。

**删的范围**：`cli.py` 的 `--from-commit` 参数与 `_cmd_land` 分支；`landing.py` 的 `_assert_reviewed_commit` 与 `:255-257` 分支；`:209`/`:239` 的短路条件随之简化。**测试同步删除**（`test_land_conflicts_and_from_commit.py:139-151`），不留空壳；同文件 `:87`/`:103` 两条 ticket-conflict 测试保留。

**不可逆点提示**：`landing.json` 一旦写出，`land` 永久拒绝（`landing.py:215-216`），`landings.jsonl` append-only，全仓**没有撤销一次落地的命令**。历史上已用 `--from-commit` 落过的地不做改写，按 ADR-0011 D2 只标注。

### D2：`repair` 禁止无证据升 `done`

**根因定位（经交叉评审修正）**：真旁路在 `lifecycle.py:188`——写回的 state 取自 `run.json.state` 本身，不是 `evidence_state()` 的结论；mismatch 只在 `evidence_state() is not None` 时才拦（`:203`）。

**门的位置必须在写之前**，不能只做事后差集断言（断言失败时 `state.json` 已写脏）。

**规则**：
- 目标状态为 `done` 时，**必须**存在 `review.json` 且 `verdict == "pass"`；否则该票不写（保持索引原值）并计入报告。
- 索引里**没有**该票时（`added` 分支），证据不满足上述条件则**不新增**。
- 写回记录增加 `status_source`：`evidence`（有 review.json pass）或 `run.json`（其它状态）。

**不采用**：`repair --accept-mismatch` 新出口（`--reason` 不可校验，会成为新的洗白入口；`retry` 与 `drop` 已覆盖人裁决）。

### D3：`command` 证据改**替换语义**

**否决计数版**：`verify.py:391-392` 已要求证据数组非空，故"每 criterion ≥1 条可复算证据"相对现状**边际作用为零**；加一条无关 `evidence/anything.txt` 即可绕过（`_evaluate_evidence` 从不校验证据与 criterion 的相关性）。

**规则**：`command` 不计入可复算证据。一个 criterion 若除去 `command` 后没有任何 `file`/`inline`/`absent` 证据，即视为"无可复算证据"，落入既有 degraded 通道（复用 `verify.py:409` 的 `all(attested)` 语义，把 command 归入 attested 侧）。

**不采用**：`verify` 重跑回执里的 `command`（撞 ADR-0012 D8「`_run_command` 只 `shell=True` + 超时」边界；且票面 `Verify` 命令**已经**在 `verify.py:647-661` 独立复跑，再加一套等于两套判据）。

**迁移注意**：`tests/test_verify_expect_exit.py:17` 断言 `attested is False`，这是**被测试钉死的既有契约**——本次是显式口径变更，需同步改该断言与 `test_cli_worktree.py:158-170`。

### D4：收口 `export.py` 第三 done 来源

`export.py:39-42` 明写「票据文件自己声明的 done 也算数」。这在"文件写了 done、但没有 run"的场景下会让票显示为已完成并解锁下游。**本批次必须先钉语义**：票面 `Status:` 是**作者标记**，不是事实（`SKILL.md:240` 已有此口径），故 `status_document` 的 `done` 集合只应来自 `states`（`state.json`），不应并入票面自述。保留一个显式豁免（例如 `--include-declared-done`）供迁移场景使用。

### H：修 env 不对称

`auto.py:107-118` 给 executor 注入七个 `DISPATCH_*`；`verify.py:249-257` **不传 `env=`**，Verify 子进程继承 CLI 进程环境。修法：让 `_run_command` 接受并传入与 executor 一致的 `DISPATCH_*`（`DISPATCH_RUN_DIR` / `EXECUTION_ROOT` / `TICKET_ID` / `RUN_ID` / `WORK_ORDER` / `TICKET_PATH` / `ATTEMPT`），其余环境保持继承（不改 `os.environ` 语义）。

## Testing Decisions

**接缝（复用现有，不新开）**：
- CLI 子进程：`run_dispatch(tmp_path, ...)`，用于 D1 / D2。
- 纯函数：`verify._evaluate_evidence`（D3，`test_verify_expect_exit.py` 已在用）、`export.status_document`（D4，纯函数最干净）。

**什么算好测试**：只测外部行为，不测实现细节。
- D1：测"CLI 不再接受该参数"（外部行为），不测"某函数不存在"。
- D2：测"`state.json` 前后 diff 里该票不变 done"，不测某个 if 分支。
- D3：给 `_evaluate_evidence` 喂三种证据组合，断言返回的 `attested` 值。
- D4：给 `status_document` 喂"无 run + 票面 done"，断言 done 集合不含它。

**仓库里可参考的先例**：`test_cli_repair.py:89`（已有 "write skips evidence mismatch"）、`test_verify_mixed_note_evidence.py:125`（已有"混用不降级"）、`test_persona_binding.py:184-196`（已有 skill_version legacy 判定）。

**必须新增的反例测试（这是本 spec 的核心价值）**：
1. `run.json={state:done}` + 三种证据全缺 + 索引无该票 → repair --write 后该票**不进 added**。
2. 同上但索引里该票为 `failed` → 仍为 `failed`。
3. `criteria[1].evidence = [command, file(evidence/anything.txt)]` → 仍判非可复算（挡掺沙）。
4. 无 run 的票 + 票面 `status: done` → `status_document` 的 done 集合不含它。

## Out of Scope

- **不补认证**。这个工具单信任主体、无认证是设计（`SKILL.md:290`、`ADR-0012 D8`），本 spec 不引入任何身份/凭据机制。
- **不给 `run.json` 加签名或哈希链**。属 hardening 级，且要改所有写 `run.json` 的地方，本批次不做。
- **不改 `dsh outcome --mark-done`**。它是文档化的看板入口（`SKILL.md:52`），本批次只保证新规则**不把它写出的 done 永久钉成 mismatch**（需在 D2 的报告中区分）。
- **不修九条 hardening**（env 全量继承、persona 路径、`dsh.py` URL 允许列表、`guard.py` hooksPath、`cli.py:2013` 死代码等），除 H 那一条 env 不对称。
- **不动审计 4 条 rejected**（含 issue 路径拼接、note 证据、persona 绝对路径、evidence `..`）：均为自影响或 hash-only，不入本次范围。
- **不改 `build/lib/` 与 `dist/` 副本**。审计只针对 `src/`；`dist/` 由 `build_skill.py` 重新生成。
- **不做 macOS 验证**（`CHANGELOG:235` 记录从未验证），本机与 CI 均不覆盖。

## Further Notes

- 审计三条均为 `needs_validation`（本机无 OS 沙箱），本次修复的**验收靠 pytest 断言**，不依赖动态复现。修复落地后，原审计的 3 条应可在有沙箱环境重跑确认。
- `adversary` 的元风险已记录：三个决策点由 brief 行号反推，可能存在未覆盖的第四处。D4 正是交叉评审补出来的第四个，说明这个风险是实的——**本 spec 不宣称覆盖全部 done 旁路**。
- 三处文档矛盾 C1/C3/C4 与代码修复**同批交付**，不允许拆到下一批。

## Confirmation

- 核对人：lead
- 日期：2026-11-02T07:23:15+00:00
- 确认方式：card
- 备注：（无）
- spec_sha256：2419d43b2cc82016003beb84f3909182292bff8ce11aab3bd7f1a1adc470a05f
