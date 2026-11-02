# 开源借鉴侦察: security-audit-fixes

Persona: builtin:oss-scout

> 角色：oss-scout（开源借鉴侦察）· 交付物 `01-oss.md` · 取证日期 **2026-11-02**
> 目标仓库：`E:\beikong-code\agent-dispatch`，HEAD `376265b59987f672bd733f69cbee140f2abb2cac`（`main`，`pyproject.toml:7` `version = "1.16.0"`）
> 本文件是本次**唯一**写入；除它以外没有改仓库里任何文件，也没有执行仓库代码/测试。

**读法与边界**

| 项 | 内容 |
|---|---|
| 信息源（允许） | `agent-dispatch` 源码；本机已装的开源参照源码（gstack / ruflo，均为完整 git checkout） |
| 信息源（本轮明确不用） | 博客/二手文章；把官方文档当证据；网络检索（本机无网可用，全程未用） |
| 我读的 agent-dispatch 内容 | `src/agent_dispatch/{landing,lifecycle,verify,ticket,review,state,export,cli}.py`、`tests/{test_land_conflicts_and_from_commit,test_cli_repair,test_verify_expect_exit,test_verify_mixed_note_evidence}.py` |
| 我没有做的 | 不跑 `pytest`、不跑 `dispatch`（本机无 OS 沙箱，按 brief 禁止执行目标代码）；不读 02-sources/03-adversary（避免互相污染取证） |

**开源参照的版本与可核对性**（两个都是本机完整 git checkout，不是网上片段）

| 代号 | 项目 | 本机路径 | 版本文件 | HEAD commit | 引用文件是否与 HEAD 一致 |
|---|---|---|---|---|---|
| **G** | gstack（MIT，`github.com/garrytan/gstack`） | `D:\obsidian_work\...\AI工具\gstack\gstack-main` | `package.json:3` `"version": "1.91.165"` | `43d6ed28f2bf55acae23a13be3d1e053f8958d3b`（2026-10-20） | 是（`git status --porcelain` 对被引文件为空） |
| **R** | ruflo / claude-flow（`github.com/ruvnet/ruflo`） | `D:\obsidian_work\...\AI工具\ruflo\ruflo-main` | `package.json:3` `"version": "3.59.0"` | `3d5742bcc5b4b1c3519447a6f4fcc52bb231e433`（2026-10-20） | 是（同上） |

---

<a id="s0"></a>
## 0. 先把三个决策点的现状钉成源码事实（这是本轮一切判断的基线）

brief 给的三个定位我逐行读过，**行为与审计描述的担心不完全一样**，先把现状写清，否则后面的"参照"会对错靶子。

### 0.1 `land --from-commit`（`landing.py:89-104`）

现状（读码，非推断）：

- `_assert_reviewed_commit()`（`landing.py:89-104`）只做一件事：拿 `verify.json` 的 `changed_files`（**文件名集合**）与 `git diff --name-only <base>..<commit>` 的结果做**集合相等**比较，不等就拒。
- 它**不核 `diff_hash`**。而同文件里正常路径 `_assert_reviewed_worktree()`（`landing.py:66-86`）核的是 `verify.json.diff_hash` == 现在重算的 `worktree_diff_hash(...)`（`landing.py:76-86`）。
- 因此两条路径的证据强度不同源：正常路径绑**内容**，`--from-commit` 只绑**文件名集合**。一个内容完全不同的提交，只要动的文件同名，就能过。
- 另外 `--from-commit` 还把两条前置门一起短路了：`landing.py:209`（worktree 必须存在）和 `landing.py:239`（run 分支必须存在）都以 `not from_commit` 为条件。
- 现存唯一测试 `tests\test_land_conflicts_and_from_commit.py:139-151`（`test_land_from_commit_restores_a_missing_worktree`）只断言 `returncode == 0` 且 `landing.json` 存在——**没有一条测试证明它会拒绝内容被替换的提交**。这就是审计能成立的原因。

### 0.2 `repair` 洗白（`lifecycle.py:62-80`）

现状（读码，非推断）：

- `evidence_state()`（`lifecycle.py:62-80`）本身是**正确**的：review > closeout > verify，三样都缺返回 `None`（不下结论）。review `pass`→`done`、`fail`→`failed`；closeout `pass`→`review`；verify `passed|degraded`→`review`、`failed`→`failed`。
- `repair()`（`lifecycle.py:176-242`）也**确实**把 `evidence_mismatch` 的票排除在写回之外（`lifecycle.py:217-222`）。
- **真正的旁路在这里**：唯一写进索引的字段是 `entry["state"]`，而 `entry["state"]` 来自 `run.json` 里的 `state` 字段本身（`lifecycle.py:188`：`"state": str(data.get("state", ""))`），**不是** `evidence_state()` 的结论。mismatch 只在 `evidence_state() is not None && expected != state` 时才被拦（`lifecycle.py:202-205`）。
- 后果：**只要 `run.json.state` 被写成 `done` 而 run 目录里根本没有任何证据文件（review/closeout/verify 全缺）**，`evidence_state()` 返回 `None`，这条票不算 mismatch、不会被拦，`--write` 直接把 `done` 抄进 `state.json`。不需要伪造任何证据文件——审计说的"洗白"，机制是**证据缺失被当成"不适用"**，而 `done` 是全系统唯一的推进开关（`export.py:20-21` 的 `_done()` 直接决定依赖是否可解锁，`export.py:28-29` 的 `_blocked_by()` 据此放行）。

### 0.3 `command` 证据（`verify.py:331-350`）

现状（读码，非推断）：

- `_evaluate_evidence()` 的 `kind == "command"` 分支（`verify.py:331-350`）只做三件事：`command` 是字符串、`exit_code`/`expect_exit` 是整数、`exit_code == expect_exit`。**不重跑、不比对任何日志、不校验 `log_hash`**，返回 `attested: False`。
- degraded 的判定是 `verify.py:409`：`bool(item_records) and all(bool(entry.get("attested")) for entry in item_records)`——即"这条 criterion 的全部证据都 attested"。所以**一条只有 `command` 证据的 criterion 不进 degraded**，可以直接拿到 `passed`。
- 而 `command` 里写的命令，跟本票 `## Verify` 里真正被复跑的 commands（`verify.py:647-661`，写日志并算 `log_hash`，`verify.py:247-273`）**是两套东西**，前者只是执行者在 `receipt.json` 里自报的一个字符串。
- 现有测试 `tests\test_verify_expect_exit.py:8-17` 明确断言 `attested is False`——即"command 不算 attested"是**被测试固定下来的既有契约**，不是遗漏。改它就是改契约（见 §5.3 的迁移口径）。

---

## 1. 判据（三个决策点共用一套，先立后评）

| # | 判据 | 为什么是它 |
|---|---|---|
| **J1** | 同一条不变量不能有两种强度口径 | `land` 的两条路径若一条核内容、一条核文件名，等于给"落地=合入已审内容"开了两种门 |
| **J2** | 门禁只能读**产物**，不能读**自述** | 执行者可写 `receipt.json` / `run.json`；门禁若采信自述，等于把写权交给被审方 |
| **J3** | 判据要有**可复现的反例测试**钉住 | 三个问题都是"现在没测试拦住"，没反例就等于没修 |
| **J4** | 变更要对历史数据有迁移口径，且**不改写历史证据** | 仓库已有先例（`docs/adr/0011` D2：旧 `verify.json` 只标 `legacy`，不重跑不覆盖） |
| **J5** | 失败必须 fail-closed，且要有**已存在**的恢复出口 | 否则修完把运维卡死 |

---

## 2. 参照清单（本文件主张的立足点，全部指到文件:函数，可用 commit 复核）

| 代号 | 位置 | 用到的机制 | 对哪个决策点 |
|---|---|---|---|
| **G1** | `bin\gstack-wtree`（93 行 bash；头注释 1-34，实现 35-93） | 工作树内容指纹 = 把工作树 stage 进临时索引后 `git write-tree`（含未跟踪、不含 ignored），**内容级**指纹 | D1 |
| **G2** | `lib\review-evidence.ts:228-278` `bindReview()` + `:280-301` `reviewFreshness()` | 评审记录绑定 `start_wtree`/`end_wtree`；状态机 `uncaptured / changed / incomplete / verified`；之后任何内容变化 → `STALE` | D1 |
| **G3** | `lib\tree-receipt.ts:132-195` `buildReceipt()`（gate 判定 164-176、`gate_reuse` 186-193）+ `:198-218` `renderReceipt()` | 树身份 + 执行身份双绑定；每个 gate 给 `reusable / rerun / not-reusable` 三态；**不把"重跑"当默认** | D1 / D3 |
| **G4** | `lib\evidence-bundle.ts:211-244` `verifyBundle()` | 每条 lane 的结论分 `verified`/`unverified`：只有**本机重跑**或**本机 ledger + 日志字节都匹配**才算 verified；`imported` 一律 `unverified` | D3 |
| **G5** | `lib\review-evidence.ts:214-226` `deriveFromFindings()` + `lib\headless-artifacts.ts:521-528` `deriveReviewStatus()` | 状态从**证据文件**派生；宣称值与派生值不符 → `REVIEW_STATUS_MISMATCH`，**整行拒绝**；`:229,:232` 显式记 `status_source: 'claimed' / 'derived'` | D2 |
| **G6** | `lib\plan-reality.ts:260-293` `checkRealityRows()` + `:253` `verdictFor()` + `:160` `RECEIPT_RE` | 每条必填行必须自带 **receipt**（`path:line` 或 commit sha）；无 receipt 的行不算行；verdict 分 `complete / incomplete / repair`，**unattended 才判死，interactive 只要求补** | D3 |
| **G7** | `lib\autoplan-run.ts:285-297` `readRecord()` + `lib\autoplan-state.ts:19-20` | 有 `INPUT: <phase> <sha256>` 行 → `receipt: 'verified'`；没有就只能 `--attest "<reason>" --attempt <id>` 绑成 `'attested'`，留 `attest_reason` | D3 |
| **R1** | `plugins\ruflo-core\scripts\witness\lib.mjs:126-187` `regenerate()` + `:206-232` `appendHistory()` | manifest 每条 fix 记 `sha256` + `markerVerified`；整份 manifest 取 hash 并签名；历史**只追加不改写** | D2 |
| **R2** | `plugins\ruflo-core\scripts\witness\lib.mjs:104-112` `refreshFix()` + `verify.mjs:70-81`（`pass / drift / regressed / missing` 四态） | **重算时把"过期/缺失"降级，绝不沿用上次结论** | D2 |
| **R3** | `v3\@claude-flow\plugin-agent-federation\src\domain\services\wg-witness-service.ts:148-161` `verifyWitnessEntry()` | 单条校验只做"重算 hash 相等 + 签名有效"，**链的完整性外推给调用方** | D2（反面参照） |

---

## 3. 决策点 1：`land --from-commit` 该删还是补内容哈希绑定

### 3.1 参照怎么做

**G1 `bin\gstack-wtree`（`43d6ed2`）**——把"内容指纹"做成唯一口径，并把为什么不能用 `HEAD^{tree}` 写进了文件头（`bin/gstack-wtree:2-14`）：

```
# gstack-wtree — print a working-tree CONTENT fingerprint (a git tree hash).
#   - Committing identical content does NOT change the fingerprint, so a
#     record made on a dirty tree stays valid after the exact same content is
#     committed (the /ship Step 5 -> Step 16 case).
#   - Untracked new source files DO change the fingerprint, so "tests passed"
#     can't stay FRESH after a new file appears.
```

它的实现方式（`bin/gstack-wtree:56,68-88`）是：`mktemp` 出一个临时索引 → 复制/`read-tree HEAD` 播种 → `git add -A` → `git write-tree` 打印树 id。**关键点是它输出的是 git 树对象 id——内容寻址，与"这份内容此刻在哪"无关**，所以同一份内容在工作树里或已提交都能算出同一个值（头注释 `:9-11` 的 "Committing identical content does NOT change the fingerprint" 说的就是这件事）。

**G2 `lib\review-evidence.ts:255-263` `bindReview()`**——把评审绑到"两端内容指纹"，并给三态：

```ts
const end = env.GSTACK_STAMP_WTREE;
const state = !start || !end ? 'uncaptured'
  : start.wtree !== end ? 'changed'
  : rec.completed !== true || rec.converged !== true ? 'incomplete' : 'verified';
```

配套的 `reviewFreshness()`（`lib/review-evidence.ts:280-301`）在**落地前**再算一次当前内容，和 `rec.wtree` 不等就 `STALE`（`:289-291`）。**注意：gstack 没有任何"从某个 commit 落地"的参数**——它只认内容指纹相等，不认"你给我一个提交我来重放"。这是本轮最值得抄的那个负数。

**G3 `lib\tree-receipt.ts:164-176`**——就算 gate 允许复用，也**不默认复用**：

```ts
if (sensitive.has(lane.label)) gates.push({ label: lane.label, verdict: 'rerun', reason: 'stamp-sensitive (reads VERSION or generated bytes); always reruns on the stamped tree', ... });
else if (!lane.verified) gates.push({ ..., verdict: 'not-reusable', ... });
else if (diffs.length) gates.push({ ..., verdict: 'not-reusable', reason: `identity changed: ${diffs.join('; ')}` });
else gates.push({ ..., verdict: 'reusable', reason: 'identity matches; tree same modulo stamps', ... });
```

### 3.2 对 agent-dispatch 的推断

- agent-dispatch 已经有**内容级**的唯一口径：`worktree_diff_hash()`（`verify.py:208-232`），并在 `docs/adr/0011` D1 里被定为唯一实现、`packet.py:60` 也取它。也就是说 D1 要的东西**项目里已经有了**，缺的只是 `--from-commit` 这条路径没用它。
- 但要用上它，必须解决一个 gstack 都不做的事：**把一个 commit 的内容还原成 worktree 口径**。`worktree_diff_hash` 吃的是 `git diff --binary <base>`（工作树 vs base）+ `ls-files --others --exclude-standard`（工作树里的未跟踪文件，`verify.py:212-231`）。对一个 commit，要复现这个哈希就必须把该 commit 的内容装进临时索引再 diff——这正是 `docs/adr/0017:11` 里已经**否决过一次**的东西（"要重放 diff，风险高"）。补内容哈希绑定 = 把被否的方案重开，成本不是打补丁。
- 恢复出口现成：worktree 丢了有 `drop`（`lifecycle.py:142-174`，归档到 `.dispatch/archive` 并写 `ledger/dropped.jsonl`）与 `gc`。J5 满足。
- 现存测试只钉了"能过"（`test_land_conflicts_and_from_commit.py:139-151`），没钉"该拒"。删掉这条路径，测试也要一并删/改，否则会留下一条永远绿的空壳。

### 3.3 结论

**建议不采用"补内容哈希绑定"，采用"删掉 `--from-commit` 这条路径"。**

不采用"补绑定"的理由（逐条对判据）：

1. **对 J1**：补绑定不是补一行校验，而是**新增第二种 diff 口径**（commit 内容 → worktree 口径）。项目已经把"哈希只有一个定义"写进 ADR-0011 D1，再开一种口径就是自己破自己的 ADR。
2. **对 J5**：不需要——`drop`/`gc` 已经是成文的恢复路径，且 ADR-0017 当初否掉 `--from-commit` 时给的替代就是它。
3. **对 J3**：删掉之后**测试要跟着删**，而不是留一条 `returncode == 0` 的空断言；补绑定的路线则要求新增"内容被替换必须拒"的反例测试，而这条反例在 commit 口径下极难写对（要构造"同名文件不同内容"且不与票面 Verify 冲突的 fixture）。

> 若甲方坚持保留：**唯一与既有定义同源的实现是"把 commit 内容装进临时索引、复用 `worktree_diff_hash` 的算法"**（G1 用的就是这个形状，见 `bin/gstack-wtree:56,68-88`）。任何"对 `git diff-tree` 文本另取一次哈希"的方案都会引入第二种口径，直接违反 ADR-0011 D1，**建议不采用**。

---

## 4. 决策点 2：`repair` 怎么让修复不新增到 `done` 的旁路

### 4.1 参照怎么做

**G5 `deriveFromFindings()`（`lib/review-evidence.ts:214-226`）**——"宣称值 vs 派生值"的处理方式是本决策点的核心参照：

```ts
const derived = deriveReviewStatus(read.rows);
const mismatches = DERIVED_KEYS.filter(key => rec[key] !== undefined && rec[key] !== derived[key])
  .map(key => `claimed ${key} ${JSON.stringify(rec[key])}, findings file has ${JSON.stringify(derived[key])}`);
if (mismatches.length) {
  throw new ReviewLogError('REVIEW_STATUS_MISMATCH', ...);
}
return { ...rec, ...derived, status_source: 'derived', findings_file: findingsPath };
```

三个可抄的点：

1. **派生值覆盖宣称值**，不是"相等才放行"——写进记录里的状态**永远**来自文件；
2. 不一致时**整条拒绝**（throw），不是"跳过并继续"；
3. 记录里留 `status_source`（`:229` 清空该键，`:232` 无 findings 文件时写 `'claimed'`，`:225` 有则写 `'derived'`）——**从来没被派生过的行自己会说是 claimed**，事后可查。

**R2 `refreshFix()`（`lib.mjs:104-112`）+ `verify.mjs:70-81`**——重算时的降级规则：

```js
const status = sha256Match && markerPresent ? 'pass'
            : (markerPresent ? 'drift' : 'regressed');
```

即：**重算不出旧值就降级，绝不"沿用上次的结论"**。文件不在时（`refreshFix` 的 `:106-108`）直接给 `_missing: true` + `markerVerified: false`，不是保留旧 `sha256`。

**R1 `appendHistory()`（`lib.mjs:206-223`）**——追加式历史：每次重算都往 `history.jsonl` 追加一条快照，**只追加不改写**，于是"这次状态变了"本身是可追溯事件。

### 4.2 对 agent-dispatch 的推断

- 现状的写法是"**声明优先、证据只用来挑刺**"：写回值取 `run.json.state`，`evidence_state()` 只用来产出 mismatch 列表（`lifecycle.py:188,202-205,217-227`）。
- G5 的写法是"**证据优先、声明只用来挑刺**"：写回值取派生值，声明值不一致就拒。**两句话正好互为镜像**——把 `lifecycle.py:188` 的 `str(data.get("state", ""))` 换成证据派生值，问题就消了。
- 但这会撞两个硬约束：
  - `evidence_state()` 会返回 `None`（三样证据全缺）。朴素替换会让 `None` 被写成状态或直接崩。R2 给的答案是**降级到"未知/不改"**，不是"当成 done"。语义上最贴的是 G5 的 `claimed`（`:232` 的措辞），落到实现就是**保持 index 原值 + 记一条 `unverified` 报告项**。
  - `run.json.state` 里的 `claimed`/`running` 这类**过程态**没有任何证据文件会派生出来（`evidence_state` 的返回域只有 `done/failed/review/None`，见 `lifecycle.py:62-80`）。所以"完全只取证据"会**丢过程态**——这是 G5 没有的问题（gstack 的 review 记录本来就只有终态）。
- 因此正确的最小改法不是"全替换"，而是**按状态分档 + 只给 `done` 加锁**：
  - 写回 `done` 时，**必须**有 `evidence_state() == 'done'`（即存在 `review.json` 且 `verdict == 'pass'`，`lifecycle.py:64-70`）；否则这条票进"不写 + 列出"。
  - 其余状态沿用 `run.json.state`，但记录 `status_source`（`evidence` / `run.json`）以便事后区分。
  - 这就把"证据缺失"从"不适用"变成"**不能升 `done`**"，正是 §0.2 里那条旁路的堵口。

### 4.3 结论

**建议采用：`done` 的写回必须由证据派生（`review.json.verdict == 'pass'`）；证据缺失只能维持原值、不能升 `done`；并给写入行加 `status_source` 来源标记。**

- 不采用"完全只取 `evidence_state()`"：会让 `claimed`/`running` 这类过程态失传（`evidence_state` 无法派生它们）。
- 不采用"只做 no-new-done 差集断言"：那是**事后断言**，断言失败时 `state.json` 已经写脏了；G5 的"派生优先"是**事前门**。两者可以都做，但门必须在写之前。
- **必须同时钉的出口（J5）**：`_cmd_repair` 今天**只按 conflicts 决定退出码**（`cli.py:2382`），mismatch 不影响退出码，容易被当成"干净"。要么让 `done` 被拒计入非零退出，要么在报告里给显式人裁决出口（例如要求先 `retry` 重跑）。

---

## 5. 决策点 3：`command` 证据按 attested / verify 重跑 / 每 criterion 至少一条可复算证据

### 5.1 参照怎么做

**G4 `verifyBundle()`（`lib/evidence-bundle.ts:211-244`）**——"自报"与"可核"被显式分成两类，且**自报永远不算 verified**：

```ts
if (o.rerun) {
  if (!same) { claims.push({ ...base, verdict: 'unverified', reason: `HEAD tree ... differs from bundle tree ...; check out ... first` }); continue; }
  const exit = run(l.command, o.repoRoot);
  const ok = exit === l.exit;
  claims.push({ ...base, verdict: ok ? 'verified' : 'unverified', rerun_exit: exit, reason: ok ? `rerun exited ${exit} as recorded` : `rerun exited ${exit}, bundle recorded ${l.exit}` });
  continue;
}
if (imported) { claims.push({ ...base, verdict: 'unverified', reason: l.reason ?? 'imported assertion; rerun to verify' }); continue; }
const record = (o.ledgerRecords ?? []).find(r => r.label === l.label && r.cmd_sha256 === l.cmd_sha256 && r.commit === l.commit);
if (!record) { claims.push({ ...base, verdict: 'unverified', reason: "no matching record in this machine's evidence ledger (produced elsewhere); rerun to verify" }); continue; }
```

关键在 `:153-156` 的 `imported` 分支：

```ts
verified: false, reason: `imported assertion from ${r.source ?? 'unknown source'}; not independently verified`,
```

**"别人报的" 在数据模型里就没有被"验证"的可能**，不是靠策略开关挡。

**G6 `checkRealityRows()`（`lib/plan-reality.ts:269-278`）**——另一个形状：**不给"降到 attested"这条路，而是要求每条必填行自带 receipt**：

```ts
for (const id of required) {
  const l = byId.get(id);
  if (!l || l.status === 'n/a') { missing.push(id); continue; }
  if (!l.receipt) { unreceipted.push(id); continue; }
  present.push(id);
}
```

receipt 的语法是 `path:line` 或 7-40 位 commit sha（`RECEIPT_RE`，`lib/plan-reality.ts:160`）——**都是可复算的东西**。然后 `verdictFor()`（`:253`）决定这个"缺 receipt"要不要判死：

```ts
const verdictFor = (ok: boolean, sessionKind?: string): RealityVerdict =>
  (ok ? 'complete' : sessionKind === 'unattended' ? 'incomplete' : 'repair');
```

**同一个事实（缺 receipt）在不同会话类型下后果不同**：无人值守判死，交互式只要求补。这是本决策点最值得抄的一条。

**G7 `readRecord()`（`lib/autoplan-run.ts:285-297`）**——"attested"在 gstack 里有**严格定义**：

```ts
if (!o.attest) throw new RunError('RESULT_RECEIPT_MISSING', `${o.record} has no INPUT: ${phase} <sha256> line; bind it on your word with --attest "<reason>" --attempt ${open.attempt}, ...`);
...
return { findings: parsed.findings, source: parsed.source, receipt: receipt.present ? 'verified' : 'attested' };
```

attested = **缺 receipt、由人显式担保并留下理由与 attempt id**。它不是"某种证据类型"，而是一次**带留痕的降级**（字段定义见 `lib/autoplan-state.ts:19-20` 的注释 `receipt?: 'verified' | 'attested'; attest_reason?: string;`）。

### 5.2 对 agent-dispatch 的推断

- agent-dispatch 现在把 `command` 写成 `attested: False`（`verify.py:346-350`），语义上等于宣称"它是可复算证据"——但它**没有可复算物**（不重跑、不比日志、不核 `log_hash`，见 §0.3）。这正是审计的落点：**分类标签与门禁强度不一致**。
- 三个候选方案对着三个参照：
  - **① 按 attested 处理** = 抄 G4 的 `imported` 语义（把"别人报的退出码"归到 unverified）。代价：`tests/test_verify_expect_exit.py:17` 会被打破，且 `SKILL.md` 里"只有 note 算 attested"的成文规则要改。
  - **② verify 重跑回执里的命令** = 抄 G4 的 `o.rerun` 分支。**但 gstack 的重跑对象是它自己 ledger 里的 lane 命令（`gstack-evidence run --label <L> -- <cmd>`，`bin/gstack-evidence:6,14-17`），不是被审方在 JSON 里写的字符串**；而且 `bin/gstack-evidence:35-37` 把两种哈希的用途写死了（`cmd_sha256` 按原样取哈希、ledger 只服务于 freshness）。agent-dispatch 若重跑 `receipt.json` 里的 `command`，执行面就从"票面 Verify"扩大到"执行者可写的任意字符串"——这与 `docs/adr/0012` D8（`verify.py` 的 `_run_command` 只做 `shell=True` + 超时）的边界相反。
  - **③ 每 criterion 至少一条可复算证据** = 抄 G6 的 `unreceipted` 形状。
- G6 还顺带回答了"要不要一刀切判死"：**不要**。agent-dispatch 里"交互式"这一侧的对应物就是 `review --accept-degraded` 这条显式出口（`review.py:69-77`）——已经有现成的降级接受机制，不需要新造开关。

### 5.3 结论

**建议采用 ①+③ 分层，不采用 ②（verify 重跑回执命令）。**

| 方案 | 结论 | 理由（对判据） | 参照 |
|---|---|---|---|
| ① `command` 按 attested 处理 | **建议采用** | 对 **J2**：现在门禁读的是自述却给了"可复算"的标签，这是标签错，不是策略选择。改成 attested 后自动落入既有的 degraded 通道（`verify.py:409`），且 `review --accept-degraded` 是既有出口（`review.py:71-77`），J5 满足 | G4 `imported → verified:false`；G7 `attested` = 缺 receipt + 显式担保 |
| ② verify 重跑 `receipt.json` 里的 `command` | **建议不采用** | 对 **J2** 反向破坏：把执行者可写的 JSON 提升成验收门要执行的 shell。gstack 的重跑只跑**自己 ledger 记过的 lane**，不是被审方声明的命令 | G4 `o.rerun`（对象不同）；`bin/gstack-evidence:14-17` |
| ③ 每 criterion ≥1 条可复算证据 | **建议采用** | 对 **J2**：把"可复算"从约定变成**结构要求**。可复算物项目里已有：`file`/`inline` 带 `sha256`、`absent`、以及 `logs/` 下复跑日志的 `log_hash`（`verify.py:247-273,302-330`） | G6 `unreceipted` + `RECEIPT_RE` |

**实施顺序（对 J4 迁移口径）**：先落 ③（结构要求；对旧回执只标 `legacy`，不重判），再落 ①（分类变更，会改变现有"纯 command 回执"的判级，必须走一次显式口径变更 + 更新被 `tests/test_verify_expect_exit.py:17` 固定的契约）。反过来做会让历史 run 同时受两种变更影响，无法归因。

---

## 6. 三个决策点共同的一个"不要抄"

**R3 `verifyWitnessEntry()`（`wg-witness-service.ts:148-161`）** 只校验"这一条的 hash 与签名"，链的完整性由调用方负责——它的注释自己写明了：

```ts
/**
 * Verify a single entry's signature + hash. Caller verifies the chain by
 * iterating entries and confirming each entry's `prevHash` equals the
 * preceding entry's `hash`.
 */
```

**建议不采用这个形状**用于 `repair` 或 `land`：agent-dispatch 的索引/落地记录是**单点裁决**，没有"调用方会把链补完"的调用方。把完整性责任外推，正是 `lifecycle.py` 今天"证据缺失 = 不适用"这条旁路在架构上的同类错误。抄 R1/R2（重算即降级、只追加不改写）即可；签名链对零第三方依赖的 Python CLI 是过重负担，也会引入密钥管理这个新攻击面。

---

## 7. 三态结论汇总

| # | 决策点 | 结论 | 一句话判据 | 主参照 |
|---|---|---|---|---|
| **D1** | `land --from-commit` | **建议不采用（删掉这条路径）**；若保留，只能改成"临时索引 + 复用 `worktree_diff_hash`"，任何"另取一次哈希"的方案建议不采用 | J1/J5：正常路径绑内容、这条只绑文件名；恢复出口已存在；ADR-0017 已否过一次 | G1 G2 G3 |
| **D2** | `repair` 洗白 | **建议采用**：`done` 的写回必须由 `review.json.verdict == 'pass'` 派生，证据缺失只能维持原值；写入行加 `status_source` | J2：写回值今天取自 `run.json.state`（自述），`evidence_state()` 只用来挑刺 | G5 R1 R2 |
| **D3** | `command` 证据 | **建议采用 ①+③ 分层**（command 记 attested + 每 criterion ≥1 条可复算证据）；**建议不采用 ② 重跑回执命令** | J2：现在的标签说它可复算，但实际不可复算；重跑则把自述变成可执行面 | G4 G6 G7 |

---

## 8. 未证实 / 我没做的事

| # | 未证实项 | 为什么 | 建议谁来证 |
|---|---|---|---|
| U1 | 审计报告原文的 3 条记录 + 9 条 hardening 具体条目 | 不在本次信息源内（brief 只给了三个落点）；我按落点取证，不猜条目 | 甲方张贴；或由 02-sources 交叉 |
| U2 | `repair` 那条旁路能否**实际**触发（`run.json.state=done` + 无任何证据文件） | 我不执行目标代码（brief 禁止）。机制是从 `lifecycle.py:188,202-205` 直接读出来的，但没跑反例 | 实现方加 fixture：造 `run.json: {"state":"done"}`、无 `review/closeout/verify`，断言 `repair --write` 后该票**不**变 done |
| U3 | `--from-commit` 是否还有别处（`auto`/`brief`）依赖 | 我只核了 `landing.py` 与 `cli.py:410-412,2977`；`auto.py` 未逐行读 | 实现方全局 grep 后再删 |
| U4 | gstack 的 `wtree` 在 Windows 上是否逐字节稳定 | `bin/gstack-wtree` 是 bash，`lib/script-invocation.ts:1-29` 专门为 Windows 找 Git Bash；本机未跑 | 若采用"临时索引"方案，必须在 CI 上加 Windows/Linux/macOS 三平台断言 |
| U5 | 把 `command` 改成 attested 后，历史 run 的判级变化幅度 | 需要跑 `verify` 才知道；我不能执行 | 实现方在迁移前后各统计一次 `status` 分布 |
| U6 | ruflo 的 witness 链能否发现"删掉中间一条" | `appendHistory` 是纯追加（`lib.mjs:206-223`），但 `loadHistory`（`:228-232`）只做解析、不做链校验 → 删除不可检测 | 只作旁证，不据此下结论 |
| U7 | 指纹对 `.gitattributes` 的 `filter`/`eol`/`working-tree-encoding` 是否敏感 | `bin/gstack-wtree:85` 通过 `git add -A` 走正常属性链，理论上会受属性转换影响；gstack 在另一处（`lib/review-evidence.ts:114-120`）显式拒绝带这些属性的文件，但 `gstack-wtree` 自身没做这层拒绝——本机未实测 | 对 D1 只是"若保留就要额外定义"的注脚，不影响结论 |

---

## 9. 复现方式（只读，任何人不需要再问我）

- **agent-dispatch 侧**：`git -C E:\beikong-code\agent-dispatch rev-parse HEAD` → `376265b59987…`；逐行读 `src/agent_dispatch/landing.py:66-104`、`src/agent_dispatch/lifecycle.py:62-80,176-242`、`src/agent_dispatch/verify.py:208-232,284-350,359-423,647-661`。
- **gstack 侧**：`git -C <gstack> rev-parse HEAD` → `43d6ed28…`；`git -C <gstack> status --porcelain -- lib/review-evidence.ts lib/evidence-bundle.ts lib/tree-receipt.ts lib/plan-reality.ts lib/autoplan-run.ts lib/autoplan-state.ts bin/gstack-wtree` → 空（被引文件与 HEAD 一致）。
- **ruflo 侧**：`git -C <ruflo> rev-parse HEAD` → `3d5742bc…`；`git -C <ruflo> status --porcelain -- plugins/ruflo-core/scripts/witness/lib.mjs plugins/ruflo-core/scripts/witness/verify.mjs v3/@claude-flow/plugin-agent-federation/src/domain/services/wg-witness-service.ts` → 空。
- **本文件没有做的事**：没跑 `pytest`、没跑 `dispatch`、没改 `E:\beikong-code\agent-dispatch` 下任何文件（本文件除外）、没联网。
