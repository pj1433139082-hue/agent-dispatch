# 仓库门禁

本文件记录 `agent-dispatch` 默认分支的门禁配置，以及怎么复核它们。

## 当前配置

- 默认分支：`main`
- 保护方式：经典分支保护（单人维护仓，不使用需要 Pro 的私有 rulesets）
- 必需状态检查：`test`，来自 `.github/workflows/ci.yml` 的 job 名
- 禁止强推、禁止删除分支
- 不要求 PR 批准（单人仓无法自己批准自己）
- 管理员保留逃生口：`enforce_admins=false`

## 本地复核

```bash
gh api repos/pj1433139082-hue/agent-dispatch/branches/main/protection
gh api repos/pj1433139082-hue/agent-dispatch/commits/main/check-runs \
  --jq '.check_runs[] | {name,status,conclusion}'
```

## 变更顺序

1. 先让 workflow 落到 `main` 并跑绿。
2. 再把 job 名写进 `required_status_checks.contexts`。
3. 开一个 PR，确认 `mergeStateStatus` 在 check 未完成时是 `BLOCKED`，完成后变 `CLEAN`。

反序操作会让所有在飞 PR 等一个永远不会产生的 check。
