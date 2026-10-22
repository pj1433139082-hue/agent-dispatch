# state-evidence-crosscheck: 状态与证据交叉校验

## What to build

现在 `run.json` 的 `state` 字段可能与证据打架：泵工程 `pw03` 的 `run.json.state=failed`，但 `verify.json.status=passed`、`closeout.json.status=pass`，而 `dispatch repair` 只信 `run.json`，于是把错的当成对的写回索引（2026-10-22 实测）。

1. 在 `lifecycle.py` 增加 `evidence_state(run_dir)`：只读 `verify.json` / `closeout.json` / `review.json`（如有），按"证据优先"推出应然状态：
   - 有 review 且 verdict=pass → `done`；verdict=fail → `failed`
   - 无 review 但 closeout.status=pass 或 verify.status∈{passed,degraded} → `review`
   - verify.status=failed → `failed`
   - 三者都缺 → `None`（不下结论）
2. `dispatch repair` 与 `dispatch status` 都增加一项 **EVIDENCE-MISMATCH**：当 `run.json.state` 与 `evidence_state` 不一致时列出来（含两者取值），退出码不变（repair 的冲突仍只由 index/disk 冲突触发）。
3. `repair --write` 遇到 mismatch 的票**不写**（与冲突票同等待遇），并在报告里列出，交给人裁决。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: src/agent_dispatch/lifecycle.py
- Write scope: tests/test_cli_repair.py
- Read scope: src/agent_dispatch/state.py
- Read scope: src/agent_dispatch/verify.py
- Read scope: src/agent_dispatch/closeout.py
- Verify: python -m pytest -q tests/test_cli_repair.py tests/test_cli_sweep.py

## Acceptance

- [ ] 造一个 run.json.state=failed 但 verify.json=passed 的票，`dispatch repair` 输出含 EVIDENCE-MISMATCH 与该票号
- [ ] 同上，`repair --write` 后该票在 state.json 里保持原值（不被写成 failed）
- [ ] 证据齐全且一致时 repair 行为不变（现有 3 条 repair 测试全绿）
- [ ] `dispatch sweep --json` 每行多一个 `evidence_state` 字段（无证据时为 null）
