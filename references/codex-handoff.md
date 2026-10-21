# Codex 工单交接

## 导出

```bash
python <技能目录>/scripts/dispatch.py export \
  --format codex \
  --tickets <票据目录> \
  --output <工单文件>
```

每张 ready 票据生成一段 work-order 风格 Markdown，包含 Owner、Risk、Goal、Write scope、Acceptance 和 Verify。

## 调用 Codex CLI

```bash
codex exec --skip-git-repo-check --ephemeral -s read-only --color never \
  -C <目标目录> -o <最后输出文件> -
```

工单内容通过 stdin 传入，不要拼成 shell 参数；在 Windows 上尤其容易被拆开。

2026-10-21 实测：`codex-cli 0.159.2` 读取 `CODEX1` 工单后精确返回：

```text
CODEX1 | python -c "print('codex-ok')"
```

这只证明工单可被 Codex CLI 消费，不代表 agent-dispatch 已实现 Codex API 客户端。
