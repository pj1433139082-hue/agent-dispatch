# 对抗审查: security-audit-fixes

Persona: builtin:adversary

| 项 | 值 |
|---|---|
| Slug | `security-audit-fixes` |
| 角色 | adversary（对抗性审查） |
| 审查日期 | 2026-11-02（+08:00） |
| 仓库版本 | `pyproject.toml:7` = `1.16.0`；HEAD `376265b` |
| 我的信息源 | **仅** `src/agent_dispatch/*.py`、`tests/*.py`、`docs/adr/*.md`、`CONTEXT.md`、`SKILL.md`、`references/ticket-contract.md` |
| 只读 | 是。未运行仓库代码/测试；本文件是本次唯一写入 |
| 隔离遵守 | 未做任何检索；先独立成稿（§1–§6），后读 `02-sources.md` 做交叉质疑（§7） |

---

## 0. 我的问题与判据

本轮要裁的三个决策点，本质是三条**不变量**能不能被代码强制。我不评"哪个方案更优雅"，只问：

1. 这个修法一旦落地，**谁能用它造出一个不该存在的 done / 一次不该存在的落地**？
2. 修法会不会**只在新的状态世界里成立**，而把历史 run 变成不可解释的灰区？
3. 修法需要删/改的东西，有没有**回不去的点**（数据已落盘、外部消费者已依赖）？
4. 每条修法都有一个**前提假设**；假设不成立时，修法不是"效果差一点"，而是**反向**（把防护变成新的绕过）。

三态口径：**建议采用 / 建议不采用 / 证据不足**。本角色要求把"方案没写出来的假设"逐条配一个**最小可证伪实验**。这些实验全部是"造一个 fixture、跑一条命令、看一眼 state.json"，**不超过 5 分钟**，任何人可复跑——但按本机约束**我没有执行**（无 OS 沙箱，禁止跑目标代码），所有实验都是**设计**，不是结果。

---

## 1. 决策点 1：`land --from-commit`（landing.py:89-104）

### 1.1 先钉住代码事实（文档里没有，来自源码）

`_assert_reviewed_commit` 的核对对象是 **文件路径集合**，不是内容：

```python
# landing.py:95-104
changed = set(str(item) for item in record.get("changed_files", []))
diff = _git(root, "diff", "--name-only", base + ".." + commit)
actual = {line.strip() for line in diff.stdout.splitlines() if line.strip()}
if actual != changed:
    raise LandingError("from-commit does not match the verified change set: ...")
```

而正常落地路径核的是 **内容哈希**：

```python
# landing.py:83-86（_assert_reviewed_worktree）
if actual != expected:
    raise LandingError("run worktree changed after verification; rerun verify and review before land")
```

**两条路径保护的完全不是同一件事**：正常路径保护"合进去的**字节**就是被 verify + review 过的那份"；from-commit 路径只保证"动的**文件名**和 verify 记录的一样"。

### 1.2 假设清单

**H1（方案假设）**：`--from-commit` 的残余风险只是"少了一道哈希"，补上内容哈希绑定就能把它抬到与正常路径同等强度。

- **这条假设是错的，且是本次最硬的一条反例。** 补 `diff-tree` 哈希 / 回放索引（`02-sources.md` §3 方案甲/乙）只能证明"这个 commit 的内容 == verify 时 worktree 的内容"。但 **from-commit 路径根本没有可用的评审对象**：
  - 该路径被设计出来的场景就是 **worktree 已丢失**（`landing.py:209`：`if not from_commit and not run.execution_root.is_dir()`）；
  - worktree 一丢，`review-packet.md` 是靠 `packet.build()` 读 `run.execution_root`、跑 `diff_digest(execution_root, base)` 生成的（`packet.py:44-50`）。`land` 默认 `require_packet=True`（`cli.py:438-444`），但它**只检查文件存不存在**（`cli.py:2950`）；
  - `review` 的自动建包是 `try/except Exception` **吞掉**的（`review.py:110-113`：`except Exception: record["packet_error"] = True`）；
  - 推论：worktree 丢失后重生成的 packet 里 `diff_hash` 为空串、`diff` 为空（`packet.py:46-50`），而 `packet.py:46` 的 `changed_files()` 在工作目录不存在时会抛 `ValueError`（`verify.py:154-159`），异常继续上抛 → 被 `review` 吞掉 → **packet 没重写，旧包留在原地，`land` 照样放行**。
- **最小可证伪实验 E1**：
  1. `render` + `start` + 写代码 + `verify`（passed）+ `review --verdict pass`（L1，带 `--packet-hash`）；
  2. 在 worktree 里 commit，取 `sha`；
  3. `git worktree remove --force <worktree>`（worktree 消失）；
  4. `dispatch review-packet <id>` **手动重生成一次** → 观察 `review-packet.md` 的 `Diff hash:` 是否变空、`## Diff` 段是否为空；
  5. `dispatch land <id> --from-commit <sha>` → 观察是否仍 exit 0 且写出 `landing.json`。
  - **证伪条件**：若第 4 步 packet 的 diff 为空、第 5 步仍成功落地，则"补哈希绑定"救不了这条路径——它救的是**已经不在场的评审对象**。

**H2（方案假设）**：删掉这条路径是可逆的、不破坏任何既有产物。

- **反例**：`land --wave` **不接受** `--from-commit`（`cli.py:2648-2651` 的 `land_run` 调用没有 `from_commit=` 参数），所以单票路径是它唯一入口；删 flag 只需同步 `cli.py:409-414`、`landing.py:183/209/239/255-257`、`_assert_reviewed_commit` 整函数、以及 `tests/test_land_conflicts_and_from_commit.py:139-151`。**改动面小、无数据迁移**——这一条我**同意**删。
- 但**残留不可逆点**：`landing.json` 一旦写出，后续 `land` 直接拒绝（`landing.py:215-216`），而 `landings.jsonl` 是 **append-only**（`landing.py:354-355`），**全仓没有任何命令能撤销一次落地**（`gc` 明确不删 `landing.json` / landing 分支：`lifecycle.py:401-403/428`）。所以"删路径"可逆，"**已经用这条路径落过的地**"不可逆——方案必须回答历史落地怎么处置。
- **最小实验 E2**：`grep -n "landing" src/agent_dispatch/lifecycle.py` → 确认 `gc` 只在 `landed_now` 时 `continue`，无 un-land 分支；再 `grep -rn "landing.json" src/` → 确认无删除者。

**H3（方案假设）**：`--from-commit` 是三个决策点里风险最高的，先删它收益最大。

- **反例（排序错误）**：它**最难被触发**（要求 worktree 已丢）且**要求先有 done**（`landing.py:195-198`）。相比之下决策点 3 的 `command` 证据**每条回执都能用、零前置条件**：一次 `{"kind":"command","command":"exit 0","exit_code":0}` 就能让一条 criterion 拿到 `passed`（`verify.py:346-350` 返回 `attested=False`；`verify.py:409` 的 degraded 只看 `attested`）。**若 9 条 hardening 要排优先级，D1 排不到第一。**
- **最小实验 E3**：读 `tests/test_cli_worktree.py:143-162` —— 现有测试把 `file + inline + absent + command + note` 五种证据塞进**同一条 criterion** 并断言 `status == "passed"`。这证明"混合证据"是**现行受测行为**，任何把 `command` 降级的修法都必须同时改这条测试——这是**迁移成本的实测锚点**，方案里没写。

### 1.3 结论

**建议采用"删路径"**，但**必须附带两条方案没写的东西**：

1. 明确保留 `_assert_reviewed_worktree` 为**唯一**落地前核对，并在 `landing.json` 里记 `verified_diff_hash`（现在 `landing.json` 根本没记它，`landing.py:317-330` 只记 `run_commit`）；
2. 对"历史上已用 `--from-commit` 落地"的 run 给处置口径（可复用 ADR-0011 D2 的"只标注不改写"先例），否则删完 flag 会让这些落地变成无主证据。

---

## 2. 决策点 2：`repair` 洗白（lifecycle.py:62-80）

### 2.1 代码事实

`repair(..., write=True)` 的写回值是 **`run.json` 的 `state` 字段**：

```python
# lifecycle.py:219-227
for ticket_id, entry in latest.items():
    if ticket_id in conflicted:
        continue
    merged[ticket_id] = {"run_id": entry["run_id"], "state": entry["state"], ...}
```

`entry["state"]` 来自 `lifecycle.py:188`（`str(data.get("state", ""))`，即 run.json）。`evidence_state()` **只用于产出 `evidence_mismatch` 报告、决定"跳不跳过"**，**从不写入**。

### 2.2 假设清单

**H4（方案假设，也是 02 的 (a)）**：把写回源从 `run.json.state` 换成 `evidence_state()` 就能堵住"洗白"。

- **这条修法在 done 这个方向上是 no-op，而且是可利用的 no-op。** `evidence_state()` 有 `done` 的唯一分支是 `review.json.verdict == "pass"`（`lifecycle.py:64-68`）；而 `run.json.state == "done"` 也只在 review 之后由 `review.py:116-118` 写入。**两个来源在 done 上恒等**，换源不改变任何一次"升到 done"的结果。真正能洗白的从来不是 state 源，而是**磁盘上的 `review.json` 本身**。
- **最小可证伪实验 E4（洗白复现，15 行）**：
  1. 造 `runs/r-01/run.json`：`{"state":"failed","ticket_id":"01","run_id":"r-01","created_at":"2026-11-01T00:00:00+00:00"}`；
  2. 同目录写 `review.json`：`{"verdict":"pass"}`（**手写，无需任何命令**）；
  3. `state.json` 里 `01` 记为 `failed`；
  4. 跑 `dispatch repair --write`；
  5. **按现有代码的预期**：`evidence_state` 判 `done` → 与 run.json 的 `failed` 不一致 → 进 `evidence_mismatch` → **这张票被跳过**。**所以洗白不发生在这一步。**
  6. **改成 run.json 的 `state="done"` 再跑一次** → `latest` 就是 `done`，与 `state.json` 的 `failed` 不一致 → 进 `state_changed`（**不是** `evidence_mismatch`，因为两者现在"一致地错"）→ **`--write` 把它写成 done**。
  - **证伪条件**：第 6 步一旦成功，说明"洗白"的真实入口是 **手改 run.json 的 state**；02 的 (a) 与 (b) **都拦不住它**（(b) 的 mismatch 依赖"证据与 state 不一致"）。
- 注意 `run.json` 是**执行者可写**的普通文件（`state.py:210-213`），而 `SKILL.md:743` 自述"共享文件系统时执行者理论上能改 `.dispatch/`"。**所以 run.json.state 与 receipt.json 同属"自报"等级**，只有 review.json / landing.json 是"异体签字"等级。**02 §4 (a) 换源后，run.json 仍可通过 `state_changed` 通道提升状态。**

**H5（02 的 (d)"no-new-done 差集断言"）**：修完之后 `done` 只能由 review 产生。

- **反例（同一 commit 里就有第二个旁路）**：`dispatch dsh mark-done` **直接** `store.set_ticket(..., "done")`，判据只有"evidence 文件存在"（`cli.py:3210-3235`）。它的记录写到 `.dispatch/external/<id>.json`，**既不过 verify 也不产生 review.json**。于是：
  - 修 `repair` 后，`done` 的合法来源变成**两个**：`review` 与 `dsh mark-done`；
  - 若该 run 的 `verify.json` 是 passed，`evidence_state` 返回 `review` → 与 `done` 不一致 → **mismatch**；
  - **结果：新修法会把 `dsh mark-done` 的 done 永远钉在"索引落后"状态**，而 mismatch 的出口是"交给人裁决"——**没有任何命令能清除这条 mismatch**（`--write` 只跳过不消除；`doctor` 会一直报 `state/evidence mismatches`，`cli.py:2011-2019`）。
- **最小实验 E5**：render + start + verify(passed) → `dispatch dsh mark-done 01 --result succeeded --evidence some.txt --task-id X` → `dispatch repair`（dry-run）→ 看是否打印 `EVIDENCE-MISMATCH 01: state=done evidence=review`。若打印，则 (b)"mismatch 一律不写"会**永久冻结一个合法 done**。

**H6（02 的 (c)"repair --accept-mismatch <id> --reason …"）**：给 mismatch 一个人裁决出口就够了。

- **反例（入口本身就是新的洗白旁路）**：这条命令的语义是"把索引写成 mismatch 里那个值"，而 mismatch 的 `state_run` 来自可写的 `run.json.state` → **等于给"run.json 自述 done"提供了一条带 `--reason` 的一次性洗白通道**，比 repair 现状更危险：它**显式**把"我接受这个不一致"变成合法动作，而 `--reason` 只是不可校验的自由文本。ADR-0008 D3 的原文是"交给人裁决"——裁决的正确形式是 **`retry`（重做）或 `drop`（归档）**，两者都已存在（`cli.py:2165-2177`、`lifecycle.py:142-174`），**不需要第三条**。
- **最小实验 E6**：拿 E4 第 6 步的 fixture，`repair --write` 后再 `repair`（dry-run）→ 观察 mismatch 列表是否**不收缩**。若 (c) 实现成"改 state.json 为 mismatch 值"，它和 E4 的洗白**结果完全相同**，只是多一行 `--reason`。

### 2.3 结论

**建议不采用** 02 的 (a) 作为主修法（它在 done 上是恒等变换），**建议采用** (b)+(e)（mismatch 不写 + 统一 `SKILL.md:328` 与 `:345` 的两说），**建议不采用** (c)（用已有的 `retry` / `drop` 替代），并**必须补一条 02 没提的**：

> `repair` 只允许写"从证据推导出、且不比现状更强的"状态——写回前断言新状态在偏序 `claimed < running < review < {done,failed}` 上不高于 `evidence_state()`，并**禁止 repair 写入 done**（`done` 只能由 `review` 与 `dsh mark-done` 写）。这条可断言、可测，且不触碰"run.json 可写"这个无法消除的假设。

---

## 3. 决策点 3：`command` 证据（verify.py:331-350）

### 3.1 代码事实

```python
# verify.py:346-350
return (
    {"kind": "command", "command": command, "exit_code": exit_code, "attested": False},
    None,
    False,          # <- attested=False
)
```

degraded 的判据是**整条 criterion 全 attested**（`verify.py:409`），所以**纯 command criterion → passed**（`verify.py:793`）。

### 3.2 假设清单

**H7（选项①"按 attested 处理"）**：把 command 的 `attested` 改成 `True` 就能让它降级，且影响可控。

- **反例（02 §5 选项① 的隐藏代价）**：选项① 会让 **`auto` 流程硬停摆**。`auto.py:472-476`：`if verify_status == "degraded" and not accept_degraded: result["status"] = "review-invalid"` —— 任何用 `command` 证据的票在 `auto --until land` 下会**当场 invalid**，而不是"降级后人工接受"。现有 `tests/test_cli_worktree.py:143-162` 那条混用五种证据并断言 passed 的用例会**直接变红**。
- **更麻烦的**：`attested` 是**布尔位**，不是等级。把 command 标 attested=True 会让 `verify.json` 里 command 与 note **不可区分**，而"可复算"与"自报"之间其实还有第三类："**已复跑**"（票面 Verify 命令真跑并记 `logs/NN.log` + `log_hash`，`verify.py:647-661`）。**用一个布尔位表达三态，会让选项③ 无处落脚。**
- **最小实验 E7**：把 `tests/test_cli_worktree.py:151` 的 command 条目删掉跑等价 fixture → 若 `status` 仍是 passed，说明混合证据不改变结论；再把**唯一**证据改成 `{"kind":"command","command":"exit 0","exit_code":0}` → 按现有代码应为 passed、退出码 0。**两者合起来证明：command 今天是一条完整的"免检通道"**，不是"辅助证据"。

**H8（选项③"每 criterion ≥1 条可复算证据"）**：它比① 更严格、更安全。

- **反例（① 与 ③ 在混合证据上互相抵消）**：
  - ③ 的判据是"该 criterion 存在至少一条 file/inline/absent（或已复跑）"。一条 criterion 同时有 command + file 时，**③ 通过**；而 **① 也不会判 degraded**（`all(attested)` 在"command 变 attested + file 不是"时为 False）。所以 **① 在混合证据下是 no-op，② 只在纯 command 下降级**；
  - 叠加后的实际规则是"混合=通过、纯 command=降级"，而"纯 note=降级、混合 note=通过"已是受测行为（`tests/test_verify_mixed_note_evidence.py:78-127`）；
  - 也就是说：**①+③ 让"掺一条可复算证据"就能洗掉自报**——这恰恰替执行者开了一条"掺沙"路径：写一条 `file` 指向任意产物即可（`verify.py:291-310`，只要文件存在，**内容无人核对**）。
- **最小可证伪实验 E8（掺沙）**：
  1. criterion 只写 `{"kind":"command","command":"exit 0","exit_code":0}` → 现状 passed；
  2. 追加 `{"kind":"file","path":"evidence/anything.txt"}`（内容 `x`，与 acceptance 毫无关系）；
  3. 预期：**按 ①+③ 组合，该 criterion 仍 passed**。
  - **证伪条件**：若第 3 步成立，"每 criterion ≥1 条可复算证据"**不构成任何新防护**——只挡住"纯 command"，挡不住"command + 一个无关文件"。

**H9（三选项共同的前提假设）**：`command` 的问题在于"没复跑"。

- **反例（复跑是伪解法）**：`_run_command` 在 `verify.py:247-273`，执行的是**回执里那条字符串**，cwd 是 `run.execution_root`。若真的"verify 重跑回执命令"：
  - 回执内容由执行者写 → **执行者写 `command: "exit 0"`，重跑仍是 0**；让可写输入变成门禁执行的代码，等于把 verify 的信任边界从"读 JSON"扩到"执行任意 shell"（`SKILL.md:743` 的"防误不防恶意"直接失效）；
  - 而票面 Verify 命令**已经复跑了**（`verify.py:647-661`），再加一条复跑通道 = **两套判据**，与 ADR-0011 D1"哈希只有一个定义"同源的病。
- **最小实验 E9**：在 E7 的 receipt 里把 command 改成 `{"command": "exit 3", "exit_code": 0}` → 现状**仍然 passed**（只比 `exit_code` 字段，`verify.py:341`）。若改成"重跑"这条会变红——但执行者只要写 `command: "exit 0"` 就能再变绿。**这就是"重跑挡不住说谎者"的最小证明。**

### 3.3 结论

- **建议不采用选项 ① 单独使用**（对 auto 是硬停摆，对混合证据是 no-op）；
- **建议不采用选项 ②**（我同意 02 的判断，且 E9 给了更强反例：重跑对 liar 无效，只对 honest-but-stale 有效）；
- **建议采用选项 ③ 的强化版**——但**不是**"每 criterion ≥1 条可复算证据"，而是 **"该 criterion 至少有一条由 verify 自己认定的物证"**：`file` 证据必须**落在 `changed_files` 里**（或 `logs/NN.log` 的 `log_hash` 对得上），否则不算"可复算"。这一条直接打死 E8 的掺沙，成本只有几行（`verify.py:284-310` 里 `execution_root` 与 `changed_files` 已在作用域内）。

---

## 4. 三条决策点共同的、方案没写出来的假设

**H10**：三个修法可以**在不改变外部可观察行为**的前提下落地。

- **反例**：任意一条都会改变 `verify.json` / `landing.json` 的**形态**，而这两个文件有多个外部消费者：`review-packet` 抓 `hashes.verify` / `hashes.receipt`（`packet.py:63-69`）、`closeout` 读 `verify.json.status`（`closeout.py:54,80-84`）、`lifecycle.evidence_state` 读 `verify.json.status`（`lifecycle.py:74-79`）、`review` / `land` 的 attestation 读 `review.json.packet_attested`（`cli.py:2546-2554`）。**改 command 的 attested 语义会让历史与新的 `verify.json` 在同一字段上有两种含义**——正是 ADR-0011 D2 要避免的，但 **02 §5 只说了"新回执写 evidence_policy"，没说历史 `verify.json` 怎么标注**。
- **最小实验 E10**：`grep -rn '"status"' src/agent_dispatch/{closeout,lifecycle,packet,review}.py` → 逐个确认消费点；只要有一个不认 `legacy` 标记，方案就漏了一处。

**H11**："verify 的门禁防误不防恶意"，所以修法只需让诚实的人不误判。

- **反例**：这句自述在本轮三个决策点里**全部被反转**：D1 的 from-commit 允许"文件名对就行"（**不需要**改文件系统）；D2 的洗白只需写一个 `run.json`（不需要任何特殊权限）；D3 的 command 是**零成本说谎**。三者的共同特征是：**攻击面不在"共享文件系统"，而在"契约本身的字段语义"**。所以这句话**不能**用来给这三条修法降级——它们连"防误"都不成立（E4 的洗白可以被一个 honest-but-confused 的执行者触发）。

---

## 5. 迁移成本与不可逆点（方案没算的四笔账）

| # | 账 | 证据 | 不可逆性 |
|---|---|---|---|
| M1 | 删 `--from-commit` 后，已有 `landing.json` 无处置口径 | `landing.py:215-216`（有 landing.json 就拒绝再次 land）、`landing.py:350-355`（ledger append-only）、`lifecycle.py:401-403/428`（gc 不碰 landing） | **高**：landing 写出后无法撤销，flag 删掉后这些地无法被机器重新解释 |
| M2 | `repair` mismatch 会永久冻结合法 done | `cli.py:2011-2019`（doctor 一直报）、`lifecycle.py:215-227`（只跳过不消除） | **中高**：`dsh mark-done` 写出的 done 会永久 mismatch（E5） |
| M3 | command 改 attested 会让 auto 硬停摆 | `auto.py:472-476`；`tests/test_cli_worktree.py:143-162` 断言 passed | **中**：有 `--accept-degraded` 逃生口，但 auto 不会自动加 |
| M4 | `_assert_reviewed_commit` 的 docstring 本身在误导：写"用 verify 记录里改过的文件清单核对"，而同一文件里另一路径核哈希 | `landing.py:83-86` vs `:90-104` | 低（文本），但会**诱导**下一个修法者以为"补哈希"是同类修复 |

---

## 6. 我给三个决策点的最终三态

| 决策点 | 我的结论 | 一句话判据 |
|---|---|---|
| D1 `land --from-commit` | **建议采用"删路径"；否决"补内容哈希绑定"** | 补哈希只能绑定"内容"，绑不住"评审对象"——worktree 一丢，`review-packet` 就是空的（E1），哈希签的是一份空 diff |
| D2 `repair` 洗白 | **建议采用 (b)+(e)+"禁写 done"断言；否决 (a) 与 (c)** | (a) 在 done 上是**恒等变换**（两来源同源于 review.json）；(c) 会把 run.json 自述提升成合法出口，而正确出口是已存在的 retry / drop |
| D3 `command` 证据 | **建议采用"③ 的强化版"（物证须落在 changed_files 或复跑日志上）；否决 ① 与 ②** | ① 让 auto 硬停摆且对混合证据 no-op；② 对 liar 无效（E9）；单纯"≥1 条可复算"挡不住掺沙（E8） |

---

## 7. 交叉质疑：读了 `02-sources.md` 之后

> 按信息源隔离，本节在独立成稿之后写。02 的证据链（A1–A20 / B1–B6 / U1–U8）我逐条对照了源码，结论是：**文档层结论大多成立，但它对源码行为的三处推断与实现不符，且这三处正好落在三个决策点上。**

### 7.1 三处"文档说 A、代码是 B"

| 02 的未证实项 | 02 的推断 | 源码事实 | 影响 |
|---|---|---|---|
| **U2**：`landing.py:89-104` 是否已核 `diff_hash` | 未证实（未读源码） | **未核**。核的是 `changed_files` **路径集合**（`landing.py:95-104`）；`diff_hash` 只在 `_assert_reviewed_worktree`（`:83-86`）用 | 02 §3 的"判据 2 不满足"**成立且更强**：两条路径不是"强度不同"，而是**核的对象不同**（路径 vs 字节） |
| **U3**：`lifecycle.py:62-80` 是否真的跳过 mismatch | 未证实；文档两说（C1） | `evidence_state()` **只读不写**（`:62-80` 全文无副作用）；写回源是 `run.json.state`（`:219-227`）。`SKILL.md:328` 属实，`SKILL.md:345` 是**过时/错误表述** | **02 的 (a) 是无效修法**（H4）。02 §4 把 (a) 列为"建议采用"第一条，**这是本轮最需要推翻的一条** |
| **U4**：`verify.py:331-350` 对 command 的实际处理 | 未证实 | 返回 `attested=False`（`:346-350`），degraded 判据是 `all(attested)`（`:409`）→ **纯 command = passed** | 02 §5 的"关键冲突"**完全成立**（README:58 vs :218 的矛盾是真的） |

### 7.2 我同意 02 的部分（列出来，避免签字时误以为只有分歧）

- **A14 与 A13 并置得出"纯 command 能拿到 passed"** —— 与我的 E7 设计同构，结论一致；
- **D1 建议删** —— 我同意删；但 02 §3 的"方案甲/乙"我反对（H1/E1：哈希绑不住评审对象），02 自己也承认"只有方案乙同源"，但方案乙仍解决不了 E1；
- **D3 选项② 不采用** —— 同意，我补了 E9；
- **C1/C2/C3 的文档两说** —— 全部属实，我另加 C7（`landing.py` docstring 自述与实现不符，见 M4）。

### 7.3 我对 02 的三条反向结论（必须带进 spec，否则会踩）

1. **02 的 D2(a)"写回状态只取自证据"是 no-op**：`evidence_state()` 判 done 的唯一依据是 `review.json.verdict=="pass"`，而 `run.json.state=="done"` 也只由 `review.py` 写入。换源不改变任何一次 done 的产生。要改的是**禁止 repair 写 done**，不是换源。
2. **02 的 D2(c)"repair --accept-mismatch"是新的洗白入口**：`--reason` 不可校验，mismatch 的 `state_run` 来自可写的 run.json；已有 `retry`（`cli.py:2165-2177`）与 `drop`（`lifecycle.py:142-174`）覆盖"人裁决"，不需要第三条。
3. **02 的 D3 组合（①+③）互相抵消**，实际规则退化成"掺一条无关 file 就洗白"（E8）。02 §5 把 ① 与 ③ 当"分层"，但在 `all(attested)` 语义下二者**不正交**：叠加后唯一还挡着的是"纯 command"，而"command + 任意 file"两边都放行。

### 7.4 02 的 U1（审计原文不可得）我的处置

02 判定"3 条记录 + 9 条 hardening 的原文在仓库里查不到"。我复核了周边事实：`docs/selection/security-audit-fixes/00-panel.json` 只是角色清单，`docs/questions/security-audit-fixes.md` 还是**未填写的问卷模板**（六个 `>` 空行全空，无任何答案）。**所以本轮三个决策点是从 brief 的三个定位反推出来的，不是从审计原文读出来的**——这意味着**修法的完整性无法验证**（可能有第 4 个决策点被漏掉）。这是本次选型最大的元风险，且它**不会**因为签字通过而消失。

---

## 8. 结论

**结论：证据不足**

理由：三个决策点的**修法方向**我有明确主张（D1 删、D2 只做 b+e+禁写 done、D3 只做强化版③），但：

- **审计原文（3 条记录 + 9 条 hardening 全文）在仓库内不可得**（与 02 的 A0-1/A0-2 及我对 `docs/questions/` 的复核一致），因此**无法验证**这三个决策点是否就是全部三条记录；
- **无法排除** 9 条 hardening 里已有条目覆盖了 D2/D3（若是，本轮修法会与既有 hardening 打架）；
- E1–E10 全部是**实验设计**，按本机约束（无 OS 沙箱、禁止执行目标代码）**没有一条被实际跑过**——"现状行为"的断言来自源码阅读，不是运行结果。

**若甲方要按推荐方向签字，建议的 `--note` 写法**：先补两件事再签 pass ——(1) 甲方张贴审计原文（至少 3 条记录 + 9 条 hardening 的条目标题）；(2) 指定一名 verifier 在隔离环境实跑 E1 / E4 / E8 三条实验（各 ≤5 分钟），结果写进 `04-*.md`。补齐后本文件三态可升为"建议采用（带条件）"。

---

## 9. 未证实清单

| 编号 | 未证实项 | 为什么没证实 | 建议怎么证 |
|---|---|---|---|
| V1 | 审计原文 3 条记录 + 9 条 hardening 全文 | 仓库内不存在（与 02 的 A0-1/A0-2 一致） | 甲方张贴 |
| V2 | E1–E10 的**实际**结果 | 本机无 OS 沙箱，禁止运行目标代码 | 隔离环境由 verifier 跑 |
| V3 | 是否存在撤销 `landing.json` 的路径 | 只读 `src/` 与 `docs/`，未穷举 `scripts/` 与 CI | `grep -rn "landing" scripts/ .github/` |
| V4 | 9 条 hardening 是否已包含 D2/D3 条目 | 同 V1 | 同 V1 |
| V5 | `dsh mark-done` 是否为现实可用的 done 旁路 | 读到 `cli.py:3210-3235` 与 parser 默认（`store_true`，默认关），未查是否有其它开关 | 读 `.dispatch/config.json` 支持键 + 跑 E5 |
| V6 | Windows/Linux 下 `git diff --name-only base..commit` 对**重命名**的表示是否一致 | 未跑 git；02 的 B 组未覆盖 | 造 rename fixture 跑一次 |
| V7 | `review-packet` 在 worktree 丢失时是否真的产出空 diff | 从 `packet.py:44-50` + `verify.py:154-159` 推出，未运行 | 这就是 E1 |
