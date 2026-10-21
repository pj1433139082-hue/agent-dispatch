# 进度与交接

## 2026-10-21 — v0.1 完成

- 按 tracer-bullet 拆成 6 张票据，全部 `done`，验收项已勾选：`.scratch/agent-dispatch-v0/issues/01..06`。
- 实现 `lint / plan / render / start / verify / review / status / export / new` 九个命令，运行时零第三方依赖。
- 全量测试 61 个通过；临时 venv 干净安装与控制台入口验证通过。
- GitHub 仓库 `pj1433139082-hue/agent-dispatch` 已建立，默认分支 `main`，MIT，public。
- CI job `test` 作为必需检查；PR #1 实测 `BLOCKED`（test queued）→ `CLEAN`（test success）后合并。
- `SECURITY.md`、`CODE_OF_CONDUCT.md`、`docs/repository-gates.md`、issue forms、PR 模板、CONTRIBUTING 已就位。

## 2026-10-21 — v0.2 DSH 看板适配

- 新增 `dsh push`：把 ready 票据以确定性 id 投递到本机 DSH 看板；只建卡，不运行卡。
- 新增 `dsh status`：读回看板状态并与 `.dispatch/dsh-map.json` 对照。
- 新增 `dsh outcome`：把外部 agent 的结果写回映射卡；不替代 `dispatch verify`。
- `dsh-board` 文件导出从裸卡数组改为完整 `create` 信封文档；`dispatch export` 仍只读。
- 全量测试从 61 增至 70；真实 50567 探针完成 create/status/outcome 与 team 父子卡验证，探针卡已清理。
- 2026-10-21 进一步实测：显式触发 teamRun 卡后，Host 真实启动 Lead + teammate，父卡摘要回传 `PARENT_PROBE_OK` 与子卡 `CHILD_PROBE_OK`；详细证据见 `docs/verification/2026-10-21-v0.2-boundaries.md`。
- Codex CLI 0.159.2 实际消费了 `dispatch export --format codex` 生成的工单；issue forms 通过 SchemaStore schema 校验；v0.2.0 GitHub Release 已发布。
- 版本升至 0.2.0；wheel 与干净 venv 控制台入口已复核。

## 已知边界

- DSH 看板卡已实际运行一次 teamRun 探针，Agent Team 真实 spawn 并回传子任务结果；但 `dispatch dsh push` 本身仍只建卡，不自动运行卡。
- 未验证 issue forms 的真实 GitHub UI 渲染；GitHub API 的 `issue_template` 仍返回 null。
- 没有实现 agent-dispatch 直接调用 Codex API；当前只保证 codex 工单可被 Codex CLI 消费。
- `dsh outcome` 写的是外部执行记录，不是本项目的验收结论；票据 done 仍必须经过 `verify` 与 `review`。
- DSH HTTP 入口是本机插件接口，不是稳定公共 API；DSH 升级后需重跑真实投递探针。
- 写域检查基于 git diff 的规范化相对路径；symlink 越界是已知限制。
- 分支保护 `enforce_admins=true`，管理员也不能绕过必需检查；紧急变更需临时关闭保护并记录。
- 项目启动的 `plan-acceptance` 由 lead 代签，不是用户亲签。

## 下一步候选

- 验证 issue forms 的 GitHub UI 渲染（需要可用的网页登录态）。
- 增加 `dsh push --update` / 归档同步，或接入 Agent Teams 的团队运行结果回读。
- 增加 Windows symlink 写域测试与发布流程。
