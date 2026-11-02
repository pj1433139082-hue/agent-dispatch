# 搜索取证: security-audit-fixes（审计 3 条 + 9 条 hardening 的修法事实）

Persona: builtin:search-scout

| 项 | 值 |
|---|---|
| Slug | `security-audit-fixes` |
| 角色 | search-scout（搜索取证） |
| 取证日期 | 2026-11-02（本地时间 14:51 +08:00） |
| 仓库版本 | `pyproject.toml:7` `version = "1.16.0"`；HEAD `376265b`（分支 `main`） |
| 上游版本 | 本机 `git version 2.56.0.windows.3` |
| 网络 | **本机可出网**（`https://example.com` HTTP 200）→ 上游官方文档为**实抓**，非记忆 |
| 信息源 | 仓库内 `docs/`、`SKILL.md`、`references/`、`tickets/`、`git help` 源文档；**未读 `src/`、`tests/`** |
| 只读 | 本文件是本次唯一写入 |

> 术语约定：本文把 brief 中的三个定位（`landing.py:89-104` / `lifecycle.py:62-80` / `verify.py:331-350`）当作**待验证的落点**，不当作已核事实——按信息源隔离，源码不作为证据源。凡"应该是什么行为"来自文档的，标【文档】；凡是我从文档推出的，标【推论】。

---

## 0. 先声明证据边界（这决定了下面哪些话能算数）

| 编号 | 事实 | 来源 | 抓取日期 | 状态 |
|---|---|---|---|---|
| A0-1 | 仓库文件清单里**不存在**本次审计报告：`git ls-files` 匹配 `security|audit` 只有 `SECURITY.md`、`docs/adr/0014-persona-binding-and-audit.md`、`docs/team/roles/auditor.md` | `git ls-files`（本机，HEAD 376265b） | 2026-11-02 | 证实 |
| A0-2 | 提交历史里**没有** `hardening` 相关提交；`audit` 相关提交 4 条（看板评审产物 / 人格审计 / 对抗审查），**无一条**包含"3 条记录 + 9 条 hardening 清单" | `git log --all --grep='hardening'`（空）、`git log --all --grep='audit'`（4 条，本机，HEAD 376265b） | 2026-11-02 | 证实 |
| A0-3 | 有"审计"作为门禁来源的先例：`1162a72`（2026-10-25）`fix: v0.88.0 - land parser actually accepts --require-attestation / --no-require-packet (audit A P0)` | `git show -s 1162a72`（本机） | 2026-11-02 | 证实 |

**结论 0**：本轮要修的 **3 条记录 + 9 条 hardening 的具体内容在仓库与提交历史里都查不到 → 未证实**。下文只针对**决策点涉及的机制**取证，不假装知道审计原文。

---

## 1. 结论速览（三态）

| # | 决策点 | 我的结论 | 一句话判据 | 支撑事实 |
|---|---|---|---|---|
| D1 | `land --from-commit` 删掉还是补内容哈希绑定 | **建议不采用（删路径）**；若要保留，只能作为"新 flag + 新 ADR 口径"，不能给现 flag 打补丁 | 同一条不变量（落地 = 合入被 verify 过的那份内容）不能有两种强度口径；ADR-0017 已否过一次，恢复路径已存在（drop/gc） | A4 A5 A7 A8 A9 A6、B1–B5 |
| D2 | `repair` 洗白（不得新增到 done 的旁路） | **建议采用**：写回状态只取自证据（verify/review/closeout），mismatch 一律不写 + 需人裁决出口 + "no new done" 差集断言 | repair 的既有定义就是"索引以磁盘为准重建"，不是"状态转移命令" | A10 A11 A12、A2、A18 |
| D3 | `command` 证据按 attested / verify 重跑 / 每 criterion ≥1 条可复算 | **建议采用 1+3（分层）**：verify 侧把 `command` 按 attested 处理（判 degraded），closeout 侧加"每 criterion 至少一条可复算证据"；**建议不采用 2（verify 重跑回执命令）** | passed 的定义已经是"所有 criterion 都有可复算证据"；而 verify 重跑回执命令 = 把执行者可写的内容提权到验收门 | A13 A14 A15 A16 A17、B4 |

---

## 2. 证据表（每条：事实 + 原文摘录 + 来源 + 抓取日期 + 版本）

### A 组 · 仓库内一手文档（版本 1.16.0 / HEAD 376265b）

> 仓库内文档没有 URL；此处给**仓库相对路径 + 行号 + 提交号**，任何人可 `git show 376265b:<path>` 复核。

| 编号 | 事实 | 原文摘录 | 位置（版本） | 抓取日期 | 状态 |
|---|---|---|---|---|---|
| A1 | 项目当前版本 1.16.0，且命令表以自动生成版为准 | `version = "1.16.0"`；「命令表以 **`docs/commands.md`（随包分发的自动生成版）** 为准…漂移即红」 | `pyproject.toml:7`、`SKILL.md:8`、`SKILL.md:463`（v1.16.0） | 2026-11-02 | 证实 |
| A2 | `land --from-commit` **今天仍在命令行里** | `dispatch land [-h] [--wave] [--dry-run] [--continue-on-error] [--from-commit FROM_COMMIT] …` | `docs/commands.md:27`（v1.16.0） | 2026-11-02 | 证实 |
| A3 | `--from-commit` 的设计理由与核对对象 | 「land --from-commit <sha>：worktree 丢失时用 commit 落地，**核对 verify 的 changed_files**。」 | `docs/CHANGELOG-2026-10.md:112,115`（v1.13.0，2026-10-31） | 2026-11-02 | 证实 |
| A4 | ADR-0017 **明确否决过** `--from-commit` | 「**Considered Options**：给 land 加 `--from-commit`（要重放 diff，风险高）**被否**，改成 drop/gc 的归档路径」 | `docs/adr/0017-error-paths-and-recovery.md:11` | 2026-11-02 | 证实 |
| A5 | ADR-0017 **没有 Status 字段**，而同目录 ADR 有 → 它是否被 v1.13.0 取代，文档里说不清 | ADR-0017 全文 13 行无 `- 状态：` 行；对照 `docs/adr/0008…md:3`「- 状态：Accepted（2026-10-22…）」、`0011…md:3`、`0012…md:3` 均有 | `docs/adr/0017…md` vs `0008/0011/0012` | 2026-11-02 | 证实（"无字段"是事实；"是否失效"未证实） |
| A6 | land 的**另一条**核对路径：票文件冲突只自动取目标分支版本，其余原样失败 | 「land 合并冲突只涉及 tickets_dir 下的文件时，自动 `git checkout --ours`（目标分支版本）并提交；**只要冲突里出现非票文件，就原样失败**」 | `docs/adr/0018-ticket-conflicts-on-land.md:3` | 2026-11-02 | 证实 |
| A7 | 项目对"diff 口径"只有**一个**定义 | 「一次 Run 的改动摘要的**唯一哈希**：`git diff --binary <base>` 的全部 tracked 改动 + 未跟踪文件内容，对字节流取 sha256；`verify.json.diff_hash` 与 `review-packet` 的 `hashes.diff` 必须是同一个值」 | `CONTEXT.md:82`（术语 Diff digest） | 2026-11-02 | 证实 |
| A8 | 唯一实现 + 历史 run 只标注不改写 | 「新增 `verify.diff_digest(root, base) -> (digest, text)` 作为**唯一**实现」「旧 `verify.json` 没有 `diff_scope` → packet 里标 `legacy_diff: true`…**不重跑、不覆盖历史证据**」 | `docs/adr/0011-diff-digest-and-review-packet.md:12,17` | 2026-11-02 | 证实 |
| A9 | 正常落地路径**已经**在核 `diff_hash` | 「land 前复核 `verify.json` 的 `diff_hash`；review 后 worktree 再被修改会拒绝，必须重新 verify/review」；「land 前会复核 verify 的 worktree diff 哈希」 | `SKILL.md:713`、`SKILL.md:746`；`references/ticket-contract.md:106` | 2026-11-02 | 证实 |
| A10 | repair 的既有语义：事实源是 run 目录，索引是缓存 | 「`dispatch repair` 从 `.dispatch/runs/*/run.json` 反向重建 `state.json`；默认 dry-run，`--write` 才落盘」「输出三分类：**新增 / 状态不一致 / 冲突**（index 与 disk 指向不同 run）。有冲突退出码 1，要人裁决」 | `docs/adr/0008-dispatch-lifecycle-and-state-recovery.md:32,33`（D3） | 2026-11-02 | 证实 |
| A11 | repair 的证据优先级与"mismatch **两说**" | 「证据优先级 **review > closeout > verify**：想造 evidence_mismatch 得改 `review.json`」「evidence_mismatch：exit **0**，但**这张票不写**（其余照写）」 **vs** 同一文件命令表「`repair`…evidence_mismatch **只打印不拦**」 | `SKILL.md:327,328` **vs** `SKILL.md:345` | 2026-11-02 | 证实（两条原文并存） |
| A12 | 已实现过一次"防洗白"设计，含验收判据 | 「`repair --write` 遇到 mismatch 的票**不写**（与冲突票同等待遇），并在报告里列出，交给人裁决」；「`repair --write` 后该票在 state.json 里保持原值（不被写成 failed）」；声称 v0.13.0 已实现 | `tickets/state-evidence-crosscheck.md:7,12,13,18,33,34` | 2026-11-02 | 证实（设计文本）；"已实现"仅凭票面自述 → 见 U5 |
| A13 | `command` 证据**不复跑** | 「`command`：执行者报告的命令与退出码；**verify 不复跑**，但 `exit_code` 必须为 0」 | `references/ticket-contract.md:74`；同句见 `README.md:218` | 2026-11-02 | 证实 |
| A14 | 但分类上 `command` **不算 attested** → 纯 command criterion 可拿到 passed | 「只有 `kind:"note"` 算 attested；**file/inline/absent/command 都不算**」；「`passed`：所有 criterion 都有可复算证据且全部 pass」 | `SKILL.md:666`、`references/ticket-contract.md:79-80`、`README.md:58-59`、`implement-skill/SKILL.md:31-32` | 2026-11-02 | 证实 |
| A15 | verify 的门禁自我定位是"防误不防恶意" | 「`verify` 的门禁**防误不防恶意**：执行者与验收者若共享同一文件系统，执行者理论上能改 `.dispatch/`；高信任要求时用独立用户/容器隔离」 | `SKILL.md:743`（安全边界） | 2026-11-02 | 证实 |
| A16 | "本机可跑/幂等/无网络"是**写作规则**，不是运行时检查；判据强度只由变异检查定义 | 「这四条是写作规则，不是运行时检查…前三条（本机/幂等/无网络）在代码里**没有实现**，靠作者自觉」「判据强度用变异检查定义…`lint` 对恒真命令报 `weak_verify` **警告**」 | `docs/adr/0012-verify-must-run-in-the-execution-environment.md:38,40`（D8/D9） | 2026-11-02 | 证实 |
| A17 | 存在"复跑"通道，但复跑的是**票面 Verify 命令**，不是回执里的 command | 「逐条按当前平台 shell 在 **execution root** 复跑票据里的 Verify 命令，退出码必须为 0；stdout/stderr 存到 logs/ 并算哈希」「`land --verify-all`…把**你给的回归命令**放进 integration branch 的临时 worktree 执行」 | `README.md:233`、`SKILL.md:492-494`、`GLOSSARY.md:34` | 2026-11-02 | 证实 |
| A18 | 文档版本号自相矛盾（不能当单一事实源） | `SECURITY.md:5`「当前只维护最新的 **0.6.x** 开发版本」 vs `pyproject.toml:7` `1.16.0` vs CHANGELOG 标题「agent-dispatch **0.1 → 1.7.2**」 | `SECURITY.md:5`、`pyproject.toml:7`、`docs/CHANGELOG-2026-10.md:1` | 2026-11-02 | 证实 |
| A19 | 架构文档自己标了同步点，落后于当前 HEAD | 「本页记录当前模块边界与数据流（**v0.10**；文档同步于提交 `c37dd2f`）」 | `docs/project/architecture.md:3`（当前 HEAD `376265b`、v1.16.0） | 2026-11-02 | 证实 |
| A20 | 架构层对 landing/verify 的职责边界（不是实现细节） | 「`verify.py`｜复跑验收命令、检查 git diff 写域、证据 sha256｜不修改票据；拒绝时写 verify.json」「`landing.py`｜把已验证 Run 合入本地 integration branch，写 landing ledger｜不 push、不切换、不合并目标分支」 | `docs/project/architecture.md:13,15` | 2026-11-02 | 证实 |

### B 组 · 上游官方文档（git 官方手册 · 抓取 2026-11-02 · 本机 git 2.56.0.windows.3）

| 编号 | 事实 | 原文摘录 | URL | 状态 |
|---|---|---|---|---|
| B1 | `git diff-tree` 的语义：比较**两棵树**的内容与模式；只给一个 tree-ish 时与父提交比 | 「Compare the content and mode of blobs found via two tree objects.」「If there is only one `<tree-ish>` given, the commit is compared with its parents (see `--stdin` below).」 | https://git-scm.com/docs/git-diff-tree ；逐字取自 https://raw.githubusercontent.com/git/git/master/Documentation/git-diff-tree.adoc | 证实（HTTP 200） |
| B2 | 不递归就只比顶层树 | 「`-r`:: Recurse into sub-trees.」 | 同上 | 证实 |
| B3 | diff-tree 支持按 pathspec 限定路径 → 可按 `changed_files` 收窄 | 「`<path>...`:: If provided, the results are limited to a subset of files matching one of the provided pathspecs.」 | 同上 | 证实 |
| B4 | 可对**任意内容**算 git 对象哈希（离线可复算，不需要 worktree 文件） | 「git-hash-object - Compute object ID and optionally create an object from a file」「`--stdin` Read the object from standard input instead of from a file.」「`-t <type>` Specify the type of object to be created (default: "blob").」 | https://git-scm.com/docs/git-hash-object | 证实（HTTP 200） |
| B5 | 可以把对象库里的内容**直接装进索引**（不需要文件在本地） | 「`--cacheinfo` is useful when the object is in the database but the file isn't available locally.」 | https://git-scm.com/docs/git-update-index | 证实（HTTP 200） |
| B6 | `git diff` 的默认比较面**不包含未跟踪文件** | NAME：「git-diff - Show changes between commits, commit and working tree, etc」；DESCRIPTION 列举：working tree↔index / index↔tree / 两树 / merge 结果 / 两 blob / 磁盘上两文件——**未提未跟踪文件** | https://git-scm.com/docs/git-diff （逐字取自 https://raw.githubusercontent.com/git/git/master/Documentation/git-diff.adoc） | 证实（HTTP 200）；对"未跟踪文件必须另取"这一点见 U6 |

---

## 3. 决策点 1：`land --from-commit`（landing.py:89-104）

**判据（三选一之前先立）**
1. 落地产物必须绑定到**被评审过的那次内容**（不是"同名文件集合"）；
2. 同一条不变量（"落地 = 合入已 verify 的内容"）不能有两种强度口径；
3. 失败模式必须 fail-closed，且要有**已存在的**恢复路径兜底。

**证据**
- 文档层面**存在直接矛盾**：ADR-0017 说该 flag「被否」，CHANGELOG v1.13.0 说「已实现」，而 ADR-0017 没有 Status 字段（A4 A5）。谁有效 → **未证实**。
- 现 flag 的核对对象是 **`changed_files` 列表**（A3），而正常落地路径核对的是 **`diff_hash`**（A9），且项目对 diff 口径规定"唯一"（A7 A8）。【推论】两条路径的证据强度不同源，等于给同一条不变量开了两种强度。
- 恢复路径已经存在：ADR-0017 否决 from-commit 时给的替代就是 drop/gc 归档（A4），且 drop/gc 在 v1.12.0 起已落地（CHANGELOG:134-135 记录 drop / gc 的存在）。

**结论：建议不采用（删掉这条路径）**
- 理由 1：判据 2 不满足，且修法成本不是"打补丁"而是"改口径"——一旦要让 from-commit 核 `diff_hash`，就必须解决"commit 的内容怎么变成 worktree 口径的 diff"，这直接触碰 ADR-0011 D1 的"唯一实现"（A8）。
- 理由 2：判据 3 已满足——worktree 丢失有 drop/gc 两步兜底（A4），不需要一条强度更低的旁路。
- 理由 3：文档已经否过一次（A4）。删路径是**恢复已被接受的设计**，不是新决策；保留才是新决策，需要新 ADR。

**若甲方坚持保留（我给的是可选项，不是推荐）——最小内容哈希绑定，只用官方机制**
- 方案甲（sha 绑定）：对 `git diff-tree -r --no-commit-id <sha> -- <changed_files...>`（B1 B2 B3）的输出取 git 对象哈希（B4），与 `verify.json.diff_hash` 比对，不符即拒。
- 方案乙（内容回放）：把 commit 的内容装进**临时索引**（B5 `--cacheinfo`），再用与 worktree 路径相同的 diff 实现复算——等价于判据 1 的"同一份内容"。
- 代价（必须写进 ADR）：两者都会引入第二种 diff 口径；方案甲比对的是"diff-tree 文本"，方案乙才接近 `CONTEXT.md:82` 的 `git diff --binary`（A7）。**只有方案乙与既有定义同源**。
- 另注：`git diff` 官方口径不含未跟踪文件（B6），而 `CONTEXT.md:82` 要求含未跟踪文件（A7）→ 无论哪个方案，"未跟踪文件如何纳入"都得单独定义（见 U6）。

**未证实**：`landing.py:89-104` 今天是否已经核 `diff_hash`；`--from-commit` 是否已被 9 条 hardening 中的某条覆盖。

---

## 4. 决策点 2：`repair` 洗白（lifecycle.py:62-80）

**判据**
1. repair 只能"重建索引"，不能变成第二条状态转移通道（A10 的定义 + `CONTEXT.md:73-74` 同一措辞）；
2. 写回值必须可回溯到证据文件，不能来自 `run.json.state` 的自述；
3. 人为裁决必须有出口，否则会长期留下"索引永远落后"的死角。

**证据**
- 既有定义：「从 `.dispatch/runs/*/run.json` 反向重建 `state.json` 的**幂等操作**…冲突要人裁决」（`CONTEXT.md:73-74`，A10）。
- 已经设计过一版防洗白：证据优先级 review > closeout > verify + EVIDENCE-MISMATCH + `--write` 跳过（A11 A12）。
- **但现状口径自相矛盾**：`SKILL.md:328`「这张票不写」与 `SKILL.md:345`「只打印不拦」（A11）——这不是实现分歧，是文档两说；写 spec 时必须先钉一个。

**结论：建议采用（组合方案，逐条给判据映射）**
- (a) **写回状态只取自证据**：`evidence_state(run_dir)` 优先 review > closeout > verify；`run.json.state` 只作为"待核字段"，不作为写入源。→ 对应判据 2。
- (b) **mismatch 一律不写**（保持 `tickets/state-evidence-crosscheck.md:13` 的原始设计），退出码仍只由 index/disk 冲突决定（该票原文就写了"退出码不变"）。→ 对应判据 1。
- (c) **人裁决出口**：新增 `repair --accept-mismatch <id> --reason <…>`（或明确要求改用 `retry`），并把裁决写进 ledger。→ 对应判据 3。**这条文档里没有先例，是新增设计，必须写进 ADR。**
- (d) **no-new-done 差集断言**：`--write` 前后做一次 state 差集，断言"没有票的状态被改成 done、没有票新增到 done 集合"；done 只能由 `review` 产生（A10 的三分类里不含"升到 done"）。→ 这是把"不新增到 done 的旁路"写成可断言的判据。
- (e) **同时钉文档两说**：把 `SKILL.md:345` 的「只打印不拦」改成与 `:328` 一致，否则下一个实现者会照 `:345` 写。

**证据强度声明**：(a)(b)(e) 有逐字条文支撑；(c)(d) 是从 A10 的定义 + ADR-0011 D2 的"历史不改写只标注"先例推出来的**新增设计**，不是文档已有内容。

---

## 5. 决策点 3：`command` 证据（verify.py:331-350）

**判据**
1. 与 `passed` 的既有定义一致（`passed` = 所有 criterion 都有**可复算**证据，A14）；
2. 不能把"验收门"变成"执行执行者给的命令"——那会让 A15 的"防误不防恶意"直接失效；
3. 变更要对历史 run 有迁移口径（先例：ADR-0011 D2 只标注不改写，A8）。

**证据（关键冲突）**
- `command` **不复跑**（A13），即"自报"；
- 但 `command` **不算 attested**（A14）→ 一个"只有 command 一条证据"的 criterion 今天可以拿到 **passed**。
- 把这两条并置：【推论】现有规则允许"执行者自报的命令 + exit_code=0"直接满足 passed 定义，与 `passed` 的书面定义（"都有可复算证据"）**冲突**。这是 9 条 hardening 里我认为最值得优先修的一条。

**三个选项逐个评估**

| 选项 | 文档一致性 | 风险 | 结论 |
|---|---|---|---|
| ① 按 attested 处理（command 不构成可复算证据 → 该 criterion 记 attested → `degraded`，需 `review --accept-degraded`） | **更一致**：与 `passed` 定义（A14）对齐；与 `degraded` 定义（只有 note 时降级）**部分冲突**，需改 `SKILL.md:666` 与 `implement-skill/SKILL.md:32` | 行为变化：现有"纯 command"回执从 passed 掉到 degraded；但有 `--accept-degraded` 逃生口，可逆 | **建议采用**（verify 侧） |
| ② verify 重跑回执里的 command | **不建议**。与 A13 的成文规则直接冲突；更糟的是把执行者可写的 JSON 内容变成验收门要执行的 shell → 直接撞 A15；ADR-0012 D8 已声明 verify 只做"起进程 + 超时"（A16），再加一条执行面等于扩大攻击面 | 高（任意命令执行 / 复现性依赖执行环境） | **建议不采用** |
| ③ 每 criterion 至少一条可复算证据 | **最一致**：`passed` 的定义就是这句（A14）；且复算物已有现成口径——`file`/`inline` 带 `sha256`、`absent`、以及 `logs/` 里复跑日志的哈希（A17、README:236） | 中：卡死的是"只写了 command"的历史回执；需要迁移口径 | **建议采用**（closeout 侧） |

**结论：①+③ 分层采用，② 不采用**
- verify 侧：`command` 不再单独构成可复算证据（判级效果 = 该 criterion attested → degraded），保留 `--accept-degraded` 这条显式的、留痕的逃生口（与 `SKILL.md:667-668` 现有"接受后 status=passed、verify_status=degraded"的记录方式一致）。
- closeout 侧：新增一条 finding「criterion 只有 command/note 证据」→ **不直接判 verify 失败**，而是让 reviewer 必须显式接受。理由：verify 判失败会让历史 run 直接变红（不可逆），而 closeout 是"收口报告"，天然适合承载"该补证据"（`land --require-closeout` 时才强制，已有开关）。
- 迁移口径沿用 ADR-0011 D2 的先例（A8）：新回执写 `evidence_policy`（或等价字段），旧 run 标 legacy，不重算、不改写。
- **必须同步改的文档**（否则 spec 一落地就与 `--check` 漂移）：`SKILL.md:666`、`README.md:218`、`references/ticket-contract.md:74`、`implement-skill/SKILL.md:32`、`docs/CHANGELOG-2026-10.md` 追加条目；并开新 ADR（现 ADR 编号到 `0020-invocation-split.md`，新条目应为 **0021**）。

---

## 6. 顺带核出来的文档矛盾（写 spec 时会踩，先列清）

| # | 矛盾 | 位置 | 对 spec 的影响 |
|---|---|---|---|
| C1 | repair 的 mismatch **只打印** vs **不写** | `SKILL.md:345` vs `SKILL.md:328` / `tickets/state-evidence-crosscheck.md:13` | 决定 D2 的实现口径，必须先钉一个 |
| C2 | repair 的三分类（新增/不一致/冲突）里**没有 mismatch** 这一类 | `docs/adr/0008…md:33`、`CONTEXT.md:73-74` | 要么扩成四分类，要么把 mismatch 归入"不一致"并说明 |
| C3 | `--from-commit`：ADR 说"被否"，CHANGELOG 说"已实现"，ADR 无 Status | `docs/adr/0017…md:11` vs `docs/CHANGELOG-2026-10.md:115` | D1 必须先裁"哪份文档有效"，否则删了是违 ADR、留着是违 ADR |
| C4 | 证据分类：README 说"可复算 / attested"两分，`command` 既"不复跑"又"不算 attested" | `README.md:58` / `:218` vs `SKILL.md:666` | D3 的核心冲突 |
| C5 | 版本号三处不同（0.6.x / 1.16.0 / 1.7.2） | `SECURITY.md:5` / `pyproject.toml:7` / `CHANGELOG:1` | 任何"版本号作为证据"的引用都要带上来源 |
| C6 | 架构文档自我标注 v0.10 / `c37dd2f`，落后 HEAD `376265b` | `docs/project/architecture.md:3` | 架构描述可作背景，不可作行号级证据 |

---

## 7. 未证实清单

| 编号 | 未证实项 | 为什么没证实 | 建议怎么证 |
|---|---|---|---|
| U1 | 审计的 3 条记录 + 9 条 hardening **全文** | 仓库/历史里不存在该报告（A0-1、A0-2） | 甲方张贴原文；本角色不猜 |
| U2 | `landing.py:89-104` 是否已核 `diff_hash`、能否被伪造 | 按信息源隔离不读源码；文档只说"land 复核 diff_hash"（A9），未说 from-commit 分支是否同样复核 | 由 verifier 在隔离环境按键读 + 写反例测试（不由本角色做） |
| U3 | `lifecycle.py:62-80` 的实际分支（是否真的跳过 mismatch） | 同上；且文档两说（C1） | 造 `run.json.state=failed`+`verify.json=passed` 的 fixture，看 `repair --write` 后 state 是否保持原值（`tickets/state-evidence-crosscheck.md:33-34` 已给了判据） |
| U4 | `verify.py:331-350` 对 `command` 的实际处理 | 同上 | 同 U3 方式 |
| U5 | `tickets/state-evidence-crosscheck.md:18` 声称的 v0.13.0 "已实现" | 票面自述，不是证据 | 查 `tests/test_cli_repair.py` 是否真有该断言（本角色不读 tests） |
| U6 | **未跟踪文件**在 from-commit 路径里如何纳入哈希 | `CONTEXT.md:82` 要求含未跟踪文件（A7）；git 官方 `git diff` 口径不含未跟踪文件（B6）；两者如何拼接属于实现口径，文档没写 | 由实现者在 ADR 里定义并给可复算公式 |
| U7 | 跨平台一致性（Windows / Linux / macOS） | 项目自述「跨平台只在 Windows（开发）与 ubuntu-latest（CI）两处验证，**macOS 未跑过**」（`docs/CHANGELOG-2026-10.md:235`）；官方文档我没有找到任何"输出逐字节跨平台一致"的原文 → 无原文可引 | 若 from-commit 改为"对 diff-tree 文本取哈希"，必须在 CI 上加 macOS/Linux 断言 |
| U8 | 上游文档与 2.56.0 的逐字等价 | 逐字引用取自 git/git `master` 分支的 Documentation 源（**未固定 tag**），HTML 页为渲染版；两者与 2.56.0 的差异未核 | 需要定版时改用 `v2.56.0` tag 的同路径文件重抓 |

---

## 8. 复现方式（只读，任何人不需再问我要上下文）

- 本地文档行号：`git show 376265b:<path>`，或直接读工作区同名文件（HEAD 与工作区一致）。
- 提交级证据：`git show -s 1162a72`、`git log --all --grep='hardening'`、`git ls-files | Select-String 'security|audit'`。
- 上游文档：上表 B 组四个 URL，抓取日期 2026-11-02，HTTP 200；逐字引用与 `Documentation/*.adoc` 源一致。
- 环境事实：`git --version` = `2.56.0.windows.3`；`git rev-parse --short HEAD` = `376265b`；`pyproject.toml:7` = `1.16.0`。

---

**给 99-summary 的一句话**：三个决策点在仓库内文档里**都有直接依据**（D1 建议删、D2 建议采用组合方案、D3 建议 ①+③ 分层），但 D1 卡在 C3（ADR 与 CHANGELOG 直接冲突，需甲方先裁哪份有效），D3 需要一次 ADR-0021 口径变更；审计原文（3+9 条）与三处源码行为**均未证实**（U1–U8）。
