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
- 2026-10-21 退役 agent-collab-runbook：源码仓库提交 `ec70c51` 并打 tag `legacy-final-2026-10-21`；`skillshare uninstall` 后 6 个 target 各 pruned 1；清理 skillshare config 的 6 处 include；`skillshare sync` 后 68 skills，agent-dispatch 安装态 0.4.0。

## 2026-10-21 — v0.5 landing 与边界实测

- 新增 `dispatch land`：把已 review 的 Run 合并到本地 integration branch（默认 `dispatch/land/<run-id>`），写 `landing.json` 与 `.dispatch/ledger/landings.jsonl`；绝不 push、绝不合并目标分支，供人工开 PR。
- land 前新增 worktree `diff_hash` 门禁：`verify` 记录完整 diff（含未跟踪文件）的哈希，land 复核；review 后再改 worktree 会被拒绝。新增对应反向测试。
- land 真实 e2e（diff_hash 门禁后）：临时 git 仓中 `lint → render → start → verify → review → land` 全通过；target `main` 保持 `42a67fff...` 不变，integration branch 为 `dispatch/land/01-20261021T130139320970Z-36be2c`，landing commit `36b9f8f63f14...`，verify `diff_hash` 前缀 `a4f4a428...`，`landing.json` 与 ledger 均写入；target 未出现该文件。另一反向 e2e：review 后修改 worktree，land 返回 1 且不写 landing 记录。
- `dsh run --rerun` 真实看板 e2e：同一 probe 卡（task_id `d102dd83-8c4f-5ef6-b0b8-464521fe299f`）第一次 execution `6619d7b5-...` succeeded；`--rerun` 后产生第二次 execution `adda3a78-...`，同样 succeeded，summary 均为 `DSH_RERUN_PROBE_OK`；探针卡已删除。
- issue forms 真实 UI 用 ego-browser 验证：Bug Report / Feature Request / Blank issue / 私有漏洞报告入口均可打开，Bug/Feature 表单字段正常；截图因窗口最小化失败，snapshot 作为证据。GitHub API 的 `issue_template` 字段仍返回 null，属于 API 枚举限制。
- 版本升至 0.5.0；全量测试 104 passed；Python 3.11 compileall 通过。详细证据见 `docs/verification/2026-10-21-v0.5-boundaries.md`。

## 2026-10-21 — v0.6 半自动推进 auto

- 新增 `dispatch auto`：自动完成 render → start → 外部执行器 → verify；执行器是用户提供的 shell 命令，dispatch 不内置模型运行时。
- 执行器在 Run 的 worktree 中运行，收到 `DISPATCH_TICKET_ID`、`DISPATCH_RUN_ID`、`DISPATCH_RUN_DIR`、`DISPATCH_EXECUTION_ROOT`、`DISPATCH_WORK_ORDER`、`DISPATCH_TICKET_PATH`、`DISPATCH_ATTEMPT`；业务文件写 worktree，`receipt.json` 与证据写 Run 目录。
- 默认 `--until review`：verify passed/degraded 后停在 review；`--max-attempts` 控制失败重试；用尽后状态 failed。每次尝试的日志与结果写 `auto/attempt-NN.log` 与 `auto.json`。
- `--until land` 要求同时提供独立 `--reviewer` 与 `--reviewer-command`；reviewer 写 `review-result.json`，只有退出码 0 且 verdict=pass 才记录 review 并 land。land 仍只建本地 integration branch，不 push、不合并目标分支。
- 新增 7 个 auto 测试：默认停在 review、失败重试成功、重试用尽失败、`--until land` 缺 reviewer-command 拒绝、reviewer pass 后 land、reviewer fail 不 land、reviewer 日志不覆盖执行器日志。
- 全量测试 111 passed；Python 3.11 compileall 通过；`dispatch --version` 为 0.6.0。
- 真实 `--until land` e2e：临时仓 target `6c9c3658...` 保持不变，Run `01-20261021T142314350916Z-1781ca`，run commit `ae3622e6...`，integration branch `dispatch/land/01-20261021T142314350916Z-1781ca`，landing commit `602bae3f...`，status=landed；integration branch 中 `src/hello.txt` 为 `hello`，target 没有该文件。
- 真实 `--until review` e2e：默认路径 exit 0、status=review、verify=passed，无 integration branch，target 不变。
- 证据见 `docs/verification/2026-10-21-v0.6-auto.md`。
- ADR 0005（auto 只编排外部执行器，不接管验收与评审）为 Accepted。

## 已知边界

- DSH 看板已实际运行 teamRun 探针，Agent Team 真实 spawn 并回传子任务结果；`dsh push` 只建卡，v0.4 新增 `dsh run` 才触发运行。
- GitHub API 的 `issue_template` 仍返回 null（UI 表单已于 2026-10-21 用 ego-browser 验证：Bug/Feature 表单可打开）。
- 没有实现 agent-dispatch 直接调用 Codex API；当前只保证 codex 工单可被 Codex CLI 消费。
- `dsh outcome` 写的是外部执行记录，不是本项目的验收结论；票据 done 仍必须经过 `verify` 与 `review`。
- DSH HTTP 入口是本机插件接口，不是稳定公共 API；DSH 升级后需重跑真实投递探针。
- 写域检查基于 git diff 的规范化相对路径；symlink 越界是已知限制。
- `dispatch auto` 会执行任意 shell 命令，只应在受信任票据与受控环境中使用；它不内置模型调用，也不自动 push/合并目标分支。重试会复用同一 worktree，不会重建 Run。
- 分支保护 `enforce_admins=true`，管理员也不能绕过必需检查；紧急变更需临时关闭保护并记录。
- 项目启动的 `plan-acceptance` 已由用户潘杰于 2026-10-21 亲签；`agent_workflow status` 显示 `plan-acceptance.passed=true`、`pending_decisions=[]`、`evidence_valid=true`。

## 下一步候选

- 增加 `land --wave` 批量按依赖顺序合入，以及恢复点/回退的显式命令。
- 增加 `auto --wave` 或 DSH 执行器适配层，但保持“外部执行器 + 本地门禁”的边界。
- 增加 `dsh push --update` / 归档同步，或接入 Agent Teams 的团队运行结果回读。
- 增加 Windows symlink 写域测试与发布流程。
