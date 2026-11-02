# 22: repair 禁止无证据升 done（含新增路径）

## What to build

写回索引的 state 直接取自 `run.json` 的 state 字段本身（`lifecycle.py:188`），`evidence_state()` 只在返回非 `None` 时做交叉检查（`:203`）。因此「`run.json` 说 done + 一个证据文件都没有」→ 返回 `None` → 不计 mismatch → `--write` 直接抄 done。**不需要伪造任何证据。**

写回 `state.json` 的四个入口：`repair --write`(cli.py:2365)、`wrap --fix`(1561)、`doctor --fix`(2055)、`gc --apply`(2329)。

**门必须在写之前**，不能只做事后差集断言（断言失败时 state.json 已写脏）。

**Blocked by:** 21
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L2
- Persona: dispatcher.md
- Write scope: src/agent_dispatch/lifecycle.py
- Write scope: tests/test_cli_repair.py
- Write scope: SKILL.md
- Read scope: src/agent_dispatch/state.py
- Read scope: docs/adr/0008-dispatch-lifecycle-and-state-recovery.md
- Verify: python -m pytest -q tests/test_cli_repair.py tests/test_repair_partial.py tests/test_cli_doctor.py

## Acceptance

- [ ] 目标为 `done` 时必须有 `review.json` 且 `verdict == "pass"`，否则该票不写并计入报告
- [ ] 索引里没有该票时（added 分支），证据不满足则**不新增**
- [ ] 写回记录含 `status_source`（值域含 `evidence` / `run.json`）
- [ ] 现有能力不回归：dry-run / 新增有证据的票 / run_id 冲突 exit 1 / mismatch 跳过
- [ ] `SKILL.md:345`「只打印不拦」改为与 `:328`「这张票不写」一致（解决 C1 矛盾）
