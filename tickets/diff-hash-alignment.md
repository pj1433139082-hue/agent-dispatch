# diff-hash-alignment: verify.diff_hash 与 review-packet 的 diff 哈希口径统一

## What to build

评审会话实测发现两个口径不一致（2026-10-22）：

- `verify.json` 的 `diff_hash` 只算 **tracked 文件**（`git diff <base> -- <files>`）；
- `review-packet` 的 `hashes.diff` 算的是**加入 new-file hunk 之后**的全文。

结果：同一个 change，两边哈希必然不同；评审说"diff_hash 对不上"，其实是口径问题，不是篡改。

1. 抽出唯一实现 `diff_for_run(root, run, files)`（放 `verify.py` 或新 `diffing.py`），`verify` 与 `packet` 都调它；
2. `verify.json` 记录 `diff_hash` 与 `diff_scope = "tracked+untracked"`（或保留旧字段另加 `diff_hash_v2`，避免历史 run 全部失真——**由实现者按向后兼容取舍并写进回执**）；
3. 旧 run（无 `diff_scope`）在 `review-packet` 里标 `legacy_diff`，不判错、只提示。

**Blocked by:** None
**Status:** done

> 2026-10-23 已实现并验证（v0.27.0，ADR-0011）。

## Dispatch

- Owner: implementer
- Risk: L2
- Write scope: src/agent_dispatch/verify.py
- Write scope: src/agent_dispatch/packet.py
- Write scope: tests/test_packet.py
- Read scope: src/agent_dispatch/state.py
- Verify: python -m pytest -q tests/test_packet.py tests/test_verify.py tests/test_cross_seat_packet.py

## Acceptance

- [ ] 同一 run 的 `verify.diff_hash` 与 `packet.hashes.diff` 一致（含新增未跟踪文件的情况）
- [ ] 不含新增文件时，旧行为不变（现有 verify / packet 测试全绿）
- [ ] 历史 run（verify.json 无新字段）走 `legacy_diff` 分支，不报错
