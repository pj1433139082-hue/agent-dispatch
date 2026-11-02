# 06 · 交叉评审（grilling 交叉轮，只读）

> 本轮规则：三个取证 agent 各读**另外两份**，各回一条反驳；本轮**任何人都不许改文件**（包括自己那份）。
> 三份反驳由 Lead 汇总，分歧结论回填 `99-summary.md` 的「决策」段。

---

## 反驳 1 — adversary 质疑 02-sources 的 D3 结论

**质疑对象**：`02-sources.md` D3「建议采用 ①+③ 分层」（L38 总结行、L154-156 实施细节）

**反驳**：02 的 ③ 是**纯计数门槛**而非**替换/绑定规则**，只在"一条可复算证据都没有"时触发；补一条无关的 `evidence/anything.txt` 即可让该 criterion 重新满足 ③，漏洞原样保留。

**依据（Lead 已独立核实）**：
- `verify.py:391-392`：证据数组为空**已经直接报错** → 现行实现本就要求「每 criterion ≥1 条证据」。
- 因此 ③ 相对现状的**边际作用只剩**「command/note 不能是唯一一条」，与"增强可复算性"无关。
- `_evaluate_evidence` **从不校验证据与 criterion 的相关性**：file 分支只核存在性 + sha256（`verify.py:291-310`），`_evidence_path` 只拒绝对路径（`verify.py:276-281`），打分按 criterion 逐条 `all()` 后取 `or`（`verify.py:389-409`）。

**连锁发现**：`01-oss.md` 的 ③ 同病（L278 也写作"每 criterion ≥1 条可复算证据"），两份独立取证都落到"计数"而非"替换"。

**要求补的证据**：fixture 令 `criteria[1].evidence = [{kind:"command"...}, {kind:"file", path:"evidence/anything.txt"}]`，断言该 criterion **仍非 attested**、verify 仍 passed、`degraded=false`。若如预期 → ③ 是空层，D3 的实际修法只剩 ①（替换语义），且 01 的"先落 ③ 再落 ①"（`01-oss.md:280`）会在真修到位前制造"洞已补"的假象。

**Lead 裁定**：**采纳反驳**。D3 采用**替换语义**（command 不计入可复算证据），否决计数版 ③。

---

## 反驳 2 — oss-scout 质疑 audit 描述（D2 真旁路位置）

**质疑对象**：审计报告 F2 的 root_cause 定位（原写"`evidence_state` 读到 review.json pass 就返回 done"）

**反驳**：真正的旁路在 `lifecycle.py:188` —— 写回索引的 state 取自 **`run.json` 的 state 字段本身**，不是 `evidence_state()` 的结论；mismatch 只在 `evidence_state() is not None` 时才拦（`:203`）。

**依据（Lead 已独立核实）**：
- `lifecycle.py:188`：`"state": str(data.get("state", ""))`
- `lifecycle.py:203`：`if (expected := evidence_state(...)) is not None`
- ⇒ 「`run.json.state=done` + 证据文件一个都没有」→ `evidence_state()` 返回 `None` → **不算 mismatch** → 直接抄 done。**不需要伪造任何证据文件**。

**要求补的证据**：fixture = `run.json {state:done}` + 无 review/closeout/verify，断言 `repair --write` 后该票**不变 done**。

**Lead 裁定**：**采纳**。审计报告的 F2 描述需修正——攻击面比原描述更宽（证据缺失即可，无需伪造）。

---

## 反驳 3 — Lead 质疑 01-oss 的实施顺序

**质疑对象**：`01-oss.md:280`「实施顺序：先落 ③ 再落 ①」

**反驳**：既然 ③ 经证实是空层，先落它**不产生任何实际修复**，却会让人误以为漏洞已补。

**依据**：见反驳 1 的核实结论。

**Lead 裁定**：**采纳**。spec 里明确否掉该顺序，实施顺序改为先 ①（替换语义），文档同步最后做。

---

## 未收敛 / 留给甲方裁定的

| 项 | 分歧 | 待裁 |
|---|---|---|
| C3 | `ADR-0017:11` 说 `--from-commit`「被否」，`CHANGELOG:115` 说「已实现」，ADR 无 Status 字段 | 哪份算数 |
| C1 | `SKILL.md:328`「这张票不写」vs `:345`「只打印不拦」 | 钉哪一条 |
| C4 | `SKILL.md:666`「只有 note 算 attested」vs `ticket-contract:79`「passed = 都有可复算证据」 | 改哪边 |

**三方一致性**：D1（`--from-commit`）三份取证**全部倾向删除**，无分歧。

---

_本文件由 Lead 汇总；三份反驳均已在源码层面独立核实，不是转述。_

---

## 反驳 3 — search-scout 质疑 01-oss 的 D2「维持原值」

**质疑对象**：`01-oss.md` §4.2/§4.3 与 §7 D2 —— 「`done` 必须由 `review.json.verdict=='pass'` 派生，**证据缺失只能维持原值**」

**反驳**：这句对它自己指认的旁路是空转。repair 写回的值就是 `latest[ticket_id]["state"]`（`lifecycle.py:188`、`:219-227`）；该值已经是 `done` 时，「维持原值」＝「把 done 写进索引」。真正拦住它的是同一行前半句那道门（必须有 `review.json.verdict=='pass'`，`lifecycle.py:64-68`），而非「缺失→维持」。

**真分歧**：oss 的「维持原值」在**索引里没有这一行**时无定义——repair 走 `added` 分支直接新增（`lifecycle.py:190`、`:219-227`）。两边都没写「没有证据时能不能新增」。

**第三来源（两边都漏，Lead 已独立核实）**：`export.py:39-42` 明写「票据文件自己声明的 done 也算数」——**无 run / 无索引行**时，票面文件写 `status: done`（`ticket.py:46` 默认值、`:157` 认该键）就直接算 done 并解锁下游。adversary 把 done 限定为「只能由 review 与 dsh mark-done 写」，同样没覆盖这条。

**要求补的证据**：
1. **E1** `run.json={"state":"done"}` + 无三样证据 + `state.json` 无该票 → `repair --write`，断言该票**不进 added**（钉死「缺失不能升 done」能否挡住**新增**路径，这是 oss 措辞的盲区）。
2. **E2** 同 fixture 但 `state.json` 里该票 `failed` → 断言仍 `failed`（这才是 oss 的「维持原值」，用于区分它与「拒绝写」）。
3. **E3** 无 run 的票 + 票面写 `status: done` → `dispatch status`，看是否已在 frontier 之外且下游解锁（钉死第三来源）。

**Lead 裁定**：**采纳**。D2 的修法必须写成「**done 只能由证据派生，且证据缺失时禁止升 done（含新增路径）**」，不能只写「维持原值」。另需为 `export.py:39-42` 的第三来源单独立项。

---

## 反驳 4 — oss-scout 质疑 adversary 的 D1 理由（结论不变，理由需要改写）

**质疑对象**：`03-adversary.md` §1.2 H1 + §6 D1「否决补内容哈希绑定」，及支撑它的 E1 / V7。

**反驳**：「从 commit 对象算内容指纹」正是 gstack 的既有做法（只读对象库、不需要工作树目录）；「worktree 丢了 packet diff 是空串」是 agent-dispatch 复用 `diff_digest(execution_root, base)` 的 fallout，**不是补哈希这个修法的属性**。

**依据（Lead 已独立核实 gstack 源码）**：
- `lib/evidence-bundle.ts:132-133`：`rev-parse HEAD` + `rev-parse HEAD^{tree}` 取 commit 与 tree 对象 ID —— 只读对象库。
- `lib/evidence-bundle.ts:212-213`：`verifyBundle` 用 `HEAD^{tree}` 比对，`same = current === o.bundle.repo.tree` —— 只有 commit 时也能比。
- `lib/gate-diff/git.ts:223-229`：`diffCommit(sha)` 用 `git diff <parent> <sha>` **从 commit 直接产 diff**。

**真实缺口被重新定位**：不是「哈希绑不住内容」，而是（a）`verify.py:97-98` 的 `_git` 写死 cwd、无 env 参数，指向临时索引要改签名或注入 `GIT_INDEX_FILE`（实现成本，非不可行）；（b）`land` 的 `--require-attestation` **默认 False**（`cli.py:438-444`），所以「评审对象可信」这件事 CLI 有能力表达，只是今天没打开。

**Lead 裁定**：**采纳**。修正如下：
- D1 的结论（删除 `--from-commit`）**不变**，但理由改写为「**否决默认配置下的补哈希**」，而不是「补哈希无效」。
- 理由从「技术不可行」改为「不值得」：补哈希需要新增第二种 diff 口径（违 ADR-0011 D1）、要改 `_git` 签名、且该能力的唯一使用场景（worktree 被毁）已有 `drop`/`gc` 出口；而 gstack 证明技术上做得到。
- **警示下一个修法者**：`landing.py:90` 的 docstring 与实现不符（自述「用文件清单核对」），会诱导人把 from-commit 改成「只核文件名 + 要求 packet 存在」——那才是真正的空签名。此风险已写入 spec 的 D1 小节。
