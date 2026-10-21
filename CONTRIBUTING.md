# Contributing

感谢参与。这个仓库很小，提交前请先读 README 与 `.scratch/agent-dispatch-v0/spec.md`。

## 本地开发

要求 Python 3.11+、git。

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

当前基线是 **97 passed**。如果测试数量变了，请同步更新本文件与 PR 模板里的数字。

## 工作方式

1. 一个改动对应一张 Markdown 票据，放在 `tickets/`；格式见 README 第 3 节。
2. 提交前跑：
   ```bash
   dispatch lint
   dispatch plan
   python -m pytest -q
   ```
3. 票据是事实源，不要手改 `dispatch` 运行目录里的 `verify.json` / `review.json` 来伪造状态。
4. 分支命名建议 `feat/<slug>`、`fix/<slug>`；提交信息用祈使句，例如 `fix: reject absolute write scopes`。
5. 合并前通过 CI 的 `test` job；单人维护仓库不强制第二人 review，但 PR 描述里要写清验证命令和结果。

## 报告问题

用仓库的 issue 表单；安全漏洞不要开公开 issue，见 `SECURITY.md`。
