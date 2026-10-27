# ADR-0011 diff 口径与评审输入（Review packet 才是被审对象）

- 状态：Accepted（2026-10-23，grill-with-docs，甲方「按照推荐」）
- 触发：实测发现同一个 change 两边哈希必然不同——`verify.worktree_diff_hash` 用 `git diff --binary --no-color <base>`（全部 tracked，无路径过滤）+ 未跟踪文件 `path\0content\0` 对字节流做 sha256；`packet.build` 用 `git diff <base> -- <files>`（文本、按文件过滤）+ 手工拼 new-file hunk，对文本做哈希。四处差异：`--binary`、路径过滤、未跟踪表示、字节 vs 文本。
- 影响：评审说"哈希对不上"其实是口径问题；更糟的是 reviewer 现在拿到的是环境变量而不是冻结输入。

## 1. 决策

### D1 哈希只有一个定义

- 新增 `verify.diff_digest(root, base) -> (digest, text)` 作为**唯一**实现；`worktree_diff_hash` 保留为薄包装（兼容旧调用）。
- `verify.json` 记录 `diff_hash` 与 `diff_scope = "tracked+untracked"`。
- `review-packet` 的 `hashes.diff` 直接取 `diff_digest`，展示用的 diff 文本另存（文本可以有多种表示，哈希只认一种）。

### D2 历史 run 不改写，只标注

- 旧 `verify.json` 没有 `diff_scope` → packet 里标 `legacy_diff: true`，并提示"哈希口径与新版不同"。
- 不重跑、不覆盖历史证据。

### D3 `auto --until land` 的评审输入强制 packet（fail-closed）

- 评审前先生成 `review-packet.md`；`DISPATCH_REVIEW_PACKET` 指向它。
- 生成失败 → 不评审（`status=review-invalid`），**不回退**到环境变量（回退会让评审质量悄悄降级）。

### D4 reviewer 回执必须回填 `packet_hash`

- review-result.json 里的 packet_hash 与实际 packet **不一致** → status=review-invalid，不 land（评错了对象）。
- 没回填 packet_hash → 记为 packet_attested=false（留痕可查），不单独判死；是否强制由 land 的策略决定。

### D5 `land` 默认要求 packet 存在

- `land` 缺 `review-packet.md` → 拒绝落地（与 `--require-closeout` 同风格，但**默认开**）。
- 逃生口 `--no-require-packet` 仅用于迁移期。

## 2. 后果

- 正面：评审对象唯一、可追溯；哈希口径不再两义；reviewer 无法"评错东西"。
- 负面：`auto --until land` 多一步生成 packet；历史 run 的旧哈希需要 `legacy_diff` 提示。
- 不解决：packet 里 diff 的**可读性**（文本表示仍是简化版，二进制内容只体现为哈希）。
