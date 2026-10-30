# 错误信息与恢复路径：每个"卡住"都要给出下一步

问题清单（2026-10-30）里反复出现的不是功能缺失，而是**卡住之后没有出路**：verify 把脏路径藏在一句通用建议后面；land 在 worktree 丢失时只能手工搬目录；retry 之后旧 receipt 仍能通过；wrap 把本地安装的 .agents/skills 当仓库污染。这一版把"状态"和"下一步"一起输出：

- **verify**：脏主检出逐条列路径（clean checkout required: N path(s) — ...），不再给"git add .gitignore"这种通用建议；新增 --allow-dirty <path> 白名单。
- **恢复**：新增 drop <id> --reason（把 run 归档到 .dispatch/archive/ 并记 ledger）；gc 对 worktree 丢失的未落地 run 报 ORPHAN 并支持 --apply 清理；gc --apply 结束自动重建索引。
- **retry**：旧 receipt 归档为 attempts/receipt-NN.json.bak 并在 run 上记 receipt_stale_at；verify 看到 stale 直接拒绝，要求重写回执。
- **wrap/doctor**：.agents/skills 只在被 git 跟踪时才算污染；doctor 丢弃索引条目时写 .dispatch/ledger/dropped.jsonl。
- **选型**：questions 不再把 Persona: 行当模板标记（team 证据自带该行）；review-window 状态移到 .dispatch/reviews/<slug>.json，不再污染 docs/selection/；panel --set role=status 标记未产出角色，team 签字时缺角色必须 --note。

**Considered Options**：给 land 加 --from-commit（要重放 diff，风险高）被否，改成 drop/gc 的归档路径；把 stale 做成软警告被否，旧证据通过等于没验。

**Consequences**：retry 之后必须重写 receipt（行为变化）；team 包多一个 panel 状态；docs/selection/ 不再出现运行态文件。
