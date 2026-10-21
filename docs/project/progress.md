# 进度与交接

## 2026-10-21 — v0.1 完成

- 按 tracer-bullet 拆成 6 张票据，全部 `done`，验收项已勾选：`.scratch/agent-dispatch-v0/issues/01..06`。
- 实现 `lint / plan / render / start / verify / review / status / export / new` 九个命令，运行时零第三方依赖。
- 全量测试 61 个通过；临时 venv 干净安装与控制台入口验证通过。
- GitHub 仓库 `pj1433139082-hue/agent-dispatch` 已建立，默认分支 `main`，MIT，public。
- CI job `test` 作为必需检查；PR #1 实测 `BLOCKED`（test queued）→ `CLEAN`（test success）后合并。
- `SECURITY.md`、`CODE_OF_CONDUCT.md`、`docs/repository-gates.md`、issue forms、PR 模板、CONTRIBUTING 已就位。

## 已知边界

- v0.1 只导出 DSH/Codex 可读载荷，不调用其真实 API；多智能体执行仍需人工粘贴或后续集成。
- 写域检查基于 git diff 的规范化相对路径；symlink 越界是已知限制。
- 分支保护 `enforce_admins=true`，管理员也不能绕过必需检查；紧急变更需临时关闭保护并记录。
- 项目启动的 `plan-acceptance` 由 lead 代签，不是用户亲签。

## 下一步候选

- 发布 v0.1.0 GitHub Release，并验证 issue forms 的 UI 渲染。
- 接入 DSH 看板/Agent Teams 的真实 API，或增加 remote runner 适配。
- 增加 Windows symlink 写域测试与发布流程。
