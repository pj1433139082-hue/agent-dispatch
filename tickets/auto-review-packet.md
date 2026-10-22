# auto-review-packet: auto 的评审输入改为 review packet

## What to build

ADR-0010 D3 写了"评审输入强制用 review packet"，但实现没跟上：`auto --until land` 的 `_review_and_land` 只把 `DISPATCH_VERIFY_JSON` 等环境变量交给 reviewer，**不生成也不传 review packet**（2026-10-22 验收时发现）。

1. `auto_protocol.py` 增加 `review_packet(root, ticket, run)`：调用 `packet.build` 生成 `.dispatch/runs/<run>/review-packet.md`（含票据快照、diff、回执、验收证据的哈希清单）。
2. `auto.py` 在 `--protocol full` 且要评审时：先生成 packet，把环境变量 `DISPATCH_REVIEW_PACKET` 指向它，再调 reviewer；reviewer 的 `review-result.json` 里若出现 `packet_hash`，必须与 packet 实际哈希一致，否则 `status=review-invalid`。
3. reviewer 命令模板（SKILL.md 里那段）改成读 `DISPATCH_REVIEW_PACKET`，不再读活动 worktree。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: src/agent_dispatch/auto_protocol.py
- Write scope: src/agent_dispatch/auto.py
- Write scope: tests/test_cli_auto_protocol.py
- Read scope: src/agent_dispatch/packet.py
- Read scope: src/agent_dispatch/review.py
- Verify: python -m pytest -q tests/test_cli_auto_protocol.py tests/test_packet.py

## Acceptance

- [ ] `auto --protocol full --until land` 后 run 目录里有 `review-packet.md`，且 reviewer 收到的 `DISPATCH_REVIEW_PACKET` 指向它
- [ ] reviewer 回执带错 `packet_hash` 时 `status=review-invalid`，不 land
- [ ] 不带 `--protocol full` 时行为不变（现有 auto 测试全绿）
- [ ] `python scripts/acceptance.py` 的 A 场景断言里加上 `review-packet.md` 存在
