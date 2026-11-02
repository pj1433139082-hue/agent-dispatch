# 21: 删除 land --from-commit 弱绑定路径

## What to build

`land` 有两条落地路径，核的却是两种强度的证据：正常路径用 `diff_hash`（字节）绑定审查对象（`landing.py:66-86`），`--from-commit` 用 `git diff --name-only` 的**路径集合**（`landing.py:89-104`），并同时短路 worktree 存在（`:209`）与 run 分支存在（`:239`）两道门。

后果：同一批文件、不同字节的 commit 可以落地，`landing.json` 照样记 `landed`。

**决定：删除整条路径**，不补哈希绑定。三条理由（见 spec §Implementation Decisions D1）：两条路径核的不是同一对象，补绑定等于新增第二种 diff 口径（违 ADR-0011 D1）；worktree 已丢时 packet 的 diff 为空，哈希签的是空 diff；成熟实现 gstack 有此绑定但无此参数。

恢复出口已存在：`drop` / `gc` 归档（`lifecycle.py:142-174`）。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L2
- Persona: dispatcher.md
- Write scope: src/agent_dispatch/landing.py
- Write scope: src/agent_dispatch/cli.py
- Write scope: tests/test_land_conflicts_and_from_commit.py
- Write scope: docs/adr/0017-error-paths-and-recovery.md
- Write scope: docs/commands.md
- Read scope: docs/specs/security-audit-fixes.md
- Read scope: docs/verification/2026-11-02-security-audit-findings.md
- Verify: python -m pytest -q tests/test_land_conflicts_and_from_commit.py tests/test_cli_land.py tests/test_land_wave.py

## Acceptance

- [ ] `dispatch land --from-commit` 不再被 CLI 接受（传了报错，而非静默忽略）
- [ ] `_assert_reviewed_commit` 已删除，落地只剩 `_assert_reviewed_worktree` 一条内容口径
- [ ] `test_land_conflicts_and_from_commit.py:139-151` 的 from-commit 测试已删；同文件 :87/:103 两条 ticket-conflict 测试保留且绿
- [ ] ADR-0017 补 Status 字段，记录 `--from-commit` 最终被 Superseded（解决 C3 矛盾）
- [ ] `docs/commands.md` 的 land 行不再列 `--from-commit`
