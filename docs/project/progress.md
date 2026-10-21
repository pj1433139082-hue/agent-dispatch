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
- 全量测试从 61 增至 74（技能层新增 4 项）；真实 50567 探针完成 create/status/outcome 与 team 父子卡验证，探针卡已清理。
- 2026-10-21 进一步实测：显式触发 teamRun 卡后，Host 真实启动 Lead + teammate，父卡摘要回传 `PARENT_PROBE_OK` 与子卡 `CHILD_PROBE_OK`；详细证据见 `docs/verification/2026-10-21-v0.2-boundaries.md`。
- Codex CLI 0.159.2 实际消费了 `dispatch export --format codex` 生成的工单；issue forms 通过 SchemaStore schema 校验；v0.2.0 GitHub Release 已发布。
- 增加自包含技能分发形态：根目录 `SKILL.md`、`scripts/dispatch.py`、`scripts/build_skill.py`；构建产物包含完整 `src/agent_dispatch`，复制到任意项目即可运行，不依赖全局安装。
- 版本升至 0.2.0；wheel 与干净 venv 控制台入口已复核。

## 2026-10-21 — v0.3 DSH 卡片变更

- 新增 `dsh update` / `dsh archive` / `dsh delete`，对应看板 `{kind:"update", taskId, patch}`、`{kind:"archive", taskId}`、`{kind:"delete", taskId}`。
- 回读验证：update 返回 title/status，archive 返回 archived_at，delete 返回 deleted=true；真实看板探针卡已清理。
- 全量测试从 74 增至 86；PR #11 合并后 main 为 `77380de`，main CI success。

## 2026-10-21 — v0.4 P0 执行隔离与判据级证据

- `render` 默认一票一 git worktree（`.dispatch/worktrees/<run-id>`，分支 `dispatch/<run-id>`），`run.json` 记 `execution_root` / `worktree_path` / `worktree_branch`；`--no-worktree` 保留逃生口，旧 run.json 回退主仓。
- verify 在 execution root 跑命令与算 diff，并额外检查 main checkout 未被污染；票据在 worktree 与主仓两处都必须保持同一哈希。
- 回执升级为 criteria 级：每条 acceptance 正好一个 criterion（id 1..N），证据支持 file/inline/absent/command/note；结论分 passed / degraded / failed。
- verify 退出码 0/2/1；degraded 可进 review，但 review 必须显式 `--accept-degraded`。
- review 成功后追加 `.dispatch/ledger/reviews.jsonl`（append-only），保留 `review.json`。
- 新增 `dsh run`（`{kind:"run", taskId}`，`--rerun` 发 rerun）；触发即返回，不等待终态。
- 版本升至 0.4.0；全量测试 97 passed；Python 3.11 compileall 通过。
- v0.4 全流程 e2e：临时 git 仓 `lint → render`（一票一 worktree）`→ start → verify`（criteria 级 file 证据，passed）`→ review`（异体 reviewer，pass）`→ status=done`；`.dispatch/ledger/reviews.jsonl` 追加一条带 `review_hash` 的记录，主检出 `git status` 干净。
- `dsh run` 真实看板 e2e：`dsh push` 创建 probe 卡（task_id `7917af3c-fcea-5624-a86e-e620d0184921`），`dsh run` 返回 action=run、status=running、execution_id `4f203757-240c-4fcb-b78f-f12257a2d402`；约 32 秒后卡片 done、execution succeeded、summary `DSH_RUN_PROBE_OK`、sessionId `session-0afddb6b-3adb-4b43-9e91-f194fe05426d`；`dsh delete` 成功。
- ADR 0003（框架项目边界）为 Proposed；ADR 0004（退役 agent-collab-runbook）为 Accepted。

- v0.4 尚未实现 `dispatch land`：ADR 已定“只建 integration branch + 人工开 PR”，代码仍是后续项。
- `rerun` envelope 仍待复测；`run` envelope 已由真实看板 e2e 验证。

## 已知边界

- DSH 看板已实际运行 teamRun 探针，Agent Team 真实 spawn 并回传子任务结果；`dsh push` 只建卡，v0.4 新增 `dsh run` 才触发运行。
- 未验证 issue forms 的真实 GitHub UI 渲染；GitHub API 的 `issue_template` 仍返回 null。
- 没有实现 agent-dispatch 直接调用 Codex API；当前只保证 codex 工单可被 Codex CLI 消费。
- `dsh outcome` 写的是外部执行记录，不是本项目的验收结论；票据 done 仍必须经过 `verify` 与 `review`。
- DSH HTTP 入口是本机插件接口，不是稳定公共 API；DSH 升级后需重跑真实投递探针。
- 写域检查基于 git diff 的规范化相对路径；symlink 越界是已知限制。
- 分支保护 `enforce_admins=true`，管理员也不能绕过必需检查；紧急变更需临时关闭保护并记录。
- 项目启动的 `plan-acceptance` 已由用户潘杰于 2026-10-21 亲签；`agent_workflow status` 显示 `plan-acceptance.passed=true`、`pending_decisions=[]`、`evidence_valid=true`。

## 下一步候选

- 验证 issue forms 的 GitHub UI 渲染（需要可用的网页登录态）。
- 增加 `dsh push --update` / 归档同步，或接入 Agent Teams 的团队运行结果回读。
- 增加 Windows symlink 写域测试与发布流程。
