# status-and-doctor-evidence-visibility: 让 status 与 doctor 看得见 state/证据不一致

## What to build

v0.13.0 引入 `lifecycle.evidence_state()` 后，`repair` 已经能用它对照 `run.json` 与证据推断应然状态，但**其余三个消费点没跟上**，导致「状态与证据打架」这件事只在 repair 的输出里露过面，日常 `status` / `doctor` 看不见，`SKILL.md` 承诺的 `EVIDENCE-BLOCKED` 也从未出现。

来源：`state-evidence-crosscheck` 的看板验收（会话 `90065d35`，2026-11-15 实测）。票面当时只把 `cli.py` 排除在写域外，这三处属票外范围，故单独开票。

三处缺口（均已实测确认行号）：

1. **`status` 从不输出 EVIDENCE-MISMATCH**。`cli.py` 里 `evidence_state` 只在第 52 行的 import 出现过一次，`_cmd_status` 全程没调用它。票面原先要求「repair 与 status 都列」，实际只有 repair 做到了。
2. **`doctor` 的 mismatch 检查是死代码**。`cli.py:2038-2044` 读 `report.get("rows", [])` 并筛 `action == "mismatch"`；而 `repair()` 返回的键是 `evidence_mismatch`（`lifecycle.py:261`），根本没有 `rows`，于是该分支永不触发。
3. **`repair` 从不打印 EVIDENCE-BLOCKED**。`SKILL.md:360` 声称会打印，实际只有 `--json` 的 `evidence_blocked` 字段有值，文本模式没有任何输出。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L2
- Persona: dispatcher.md
- Requires: local
- Write scope: src/agent_dispatch/cli.py
- Write scope: tests/test_cli_repair.py
- Write scope: tests/test_cli_doctor.py
- Read scope: src/agent_dispatch/lifecycle.py
- Read scope: SKILL.md
- Verify: python -m pytest -q tests/test_cli_repair.py tests/test_cli_sweep.py tests/test_cli_doctor.py

## Acceptance

- [ ] `status` 的文本模式与 `--json` 都列出 state 与证据不一致的票（含 run.json 值与证据推出值两值）；**退出码不变**（status 仍是只读查询，不因 mismatch 变成非零）
- [ ] `doctor` 改读 `report["evidence_mismatch"]`，能真的报出不一致并给出 `run dispatch repair --write` 提示；原有 `rows`/`action=="mismatch"` 死代码删除
- [ ] `repair` 文本模式补打印 `EVIDENCE-BLOCKED <票号>: state=<run.json 值>`，与 `SKILL.md:360` 的承诺对齐；`--json` 输出不变
- [ ] 既有行为不回归：`repair` 仍不写有 mismatch 的票、`sweep --json` 的 `evidence_state` 字段不变、doctor 其余检查项不受影响
