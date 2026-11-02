# 选型结论: security-audit-fixes

> 汇总各角色证据后填这张表；**结论由甲方签字才算过**（ADR-0007 Q1）。
>
> 产物模式：team（每份证据由独立子会话产出，文件头必须带 Persona 行）

| 角色 | 结论 | 证据位置 | 未证实项 |
|---|---|---|---|
| 开源借鉴侦察（oss-scout） | D1 删路径 / D2 done 须由证据派生 / D3 ①+③ 分层（被交叉评审修正为替换语义） | 01-oss.md | 旁路未跑反例；auto.py 未逐行读 |
| 搜索取证（search-scout） | D1 删路径 / D2 组合方案 / D3 ①+③；并提出三处文档矛盾 C1/C3/C4 | 02-sources.md | 审计原文不可得；三处行为未证实 |
| 对抗性审查（adversary） | **结论=证据不足**；D1 删路径、否决补哈希；D2 禁 repair 写 done；D3 采纳替换语义 | 03-adversary.md | E1-E10 全为实验设计，一条未跑 |

## 决策

- **采用**：
  - **D1** 删除 `land --from-commit` 整条路径。三份取证一致；补内容哈希绑定会新增第二种 diff 口径，违反 ADR-0011 D1「哈希只有一个定义」；gstack 有 review↔内容绑定但**无**「从 commit 落地」参数。
  - **D2** `done` 只能由证据派生，且**证据缺失时禁止升 done，含新增路径**。真旁路在 `lifecycle.py:188`（写回的 state 取自 `run.json.state` 本身）；`evidence_state()` 返回 `None` 时不计 mismatch。
  - **D3** `command` 证据采用**替换语义**：command 不计入可复算证据，criterion 须另有 `file`/`inline`/`absent`/`log_hash`。否决计数版（`verify.py:391-392` 已要求非空数组，计数版是空层，可被无关 file 掺沙绕过）。
  - **H** `verify._run_command` 补与 executor 一致的 `DISPATCH_*` 环境，修「对执行者通过、对门禁失败」的不对称。
  - **D4（新，交叉评审新增）** `export.py:39-42` 的第三 done 来源需单独立项收口。
- **不采用**：
  - 补内容哈希绑定 `--from-commit`（无效：worktree 丢失时 packet diff 为空，两条路径核的不是同一对象）。
  - `repair --accept-mismatch` 新出口（会成为新洗白入口；`retry` 与 `drop` 已覆盖人裁决）。
  - `verify` 重跑回执里的 `command`（撞 ADR-0012 D8；票面 Verify 已复跑）。
  - 计数版 ③，以及「先落 ③ 再落 ①」的顺序（会在真修到位前制造「洞已补」假象）。
- **理由**：见 `06-cross-review.md` 的三条反驳与 Lead 裁定。

## 待甲方裁定（阻塞 spec）

| 编号 | 矛盾 | 建议 |
|---|---|---|
| C3 | `ADR-0017:11` 说 `--from-commit`「被否」 vs `CHANGELOG:115` 说「已实现」，ADR 无 Status 字段 | 按 D1 删除，ADR 补 Status: Superseded |
| C1 | `SKILL.md:328`「这张票不写」 vs `:345`「只打印不拦」 | 以代码为准（不写），改 `:345` |
| C4 | `SKILL.md:666`「只有 note 算 attested」 vs `ticket-contract:79`「passed = 都有可复算证据」 | 以 ticket-contract 为准，D3 落地时同改 `:666` |
| Q10 | 审计原文（3+9 条）不在仓库内，adversary 因此判「证据不足」 | 建议复制进 `docs/verification/` |

## 甲方签字

- 签字人：lead
- 日期：2026-11-02
- 备注：adversary 结论为证据不足（审计原文不在仓库）；甲方已选择将审计原文入库。三条交叉评审反驳已并入 06-cross-review.md 并经 Lead 源码级核实。D3 由计数版修正为替换语义；D2 补上新增路径盲区；新增 D4（export.py:39-42 第三 done 来源）。
- 选择：☑ 通过　☐ 有保留通过　☐ 打回
- 确认方式：card
