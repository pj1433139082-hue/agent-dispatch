# 派单台 · agent-dispatch

> **ask-matt 决定做什么、先后做什么；dispatch 决定谁做、能写哪、拿什么证据。**

`agent-dispatch` 是一个文件优先的任务编排分发 CLI。它把“票据”变成可执行的工单，把执行者的回执交给独立验收门禁，再交给异体评审，最后才允许票据进入 `done`。

当前版本以 `pyproject.toml` 为准（`dispatch --version` 同值），Python 3.11+，运行时只用标准库；pytest 仅用于本项目开发测试。版本变化：v0.2 DSH 看板适配；v0.2.1 跨项目路径与 Windows verify 修复；v0.3 看板卡片 update / archive / delete；v0.4 一票一 worktree + 判据级证据 + review ledger + `dsh run`；v0.5 `dispatch land`（只建本地 integration branch，人工开 PR）；v0.6 `dispatch auto`（外部执行器 + 重试）；v0.7 Persona 人设字段与 `assign` / `personas`；v0.7.1 上下文包 `context`、两阶段 `brief` 门禁、`auto` 失败回灌；v0.8.0 运行检查点 `checkpoint` 与收口报告 `closeout`；v0.9.0 需求对齐薄包装 `align` / `spec` / `tickets`（问卷分级 + 交付标准切票）。

> 本仓库同时是 `agent-dispatch` 技能包：根目录有 `SKILL.md`，`scripts/dispatch.py` 可直接从仓库运行，`scripts/build_skill.py` 生成可复制到其他项目的干净技能目录。见第 9 节。

---

## 1. 它解决什么问题

多智能体协作里常见的三个漏洞：

1. **票据没有契约**：只有一句“做一下 X”，没有写域、验收命令、依赖边。
2. **执行者自己宣布完成**：改完代码就说 done，没有独立复跑和 diff 检查。
3. **评审不是异体**：实现者自己 review 自己，或者根本没有评审记录。

派单台把这三件事变成硬门禁：

- 票据是 Markdown，一票一文件，可 diff、可 review、可进 Git。
- 执行者只能写 `receipt.json`，**不能改票据状态**；状态只能由 `verify` / `review` 改。
- `render` 默认给每张票创建独立的 git worktree 与 `dispatch/<run-id>` 分支；执行根与主检出分离，`--no-worktree` 只作为逃生口。
- 执行者的回执按验收项给出 criteria 级证据；`verify` 复跑票内命令、检查真实 git diff 是否越出写域，并把证据分为可复算 / attested。
- `verify` 的结论是 `passed` / `degraded` / `failed`；degraded 必须由评审显式 `--accept-degraded` 才能放行。
- `review` 要求评审者不是票据 owner，也不是实际领取人；L4 风险必须显式 `--human`；每次有效评审追加到 `.dispatch/ledger/reviews.jsonl`。

v0.6 仍刻意不做：Web UI、多用户权限、云沙箱、自动 push、自动合并目标分支、恢复点、内建 agent 运行时。`dispatch auto` 只调用你提供的外部命令，不内置模型调用；它把“票据 → 工单 → 回执 → 验收 → 评审 → 状态/导出/投递/触发/半自动推进”串成最小闭环。

---

## 2. 核心对象

| 对象 | 存在形式 | 作用 |
|---|---|---|
| **Ticket 票据** | `tickets/<id>-<slug>.md` | 需求、依赖、写域、验收命令的唯一事实源 |
| **Run 运行** | `.dispatch/runs/<run-id>/` | 一次领取；包含 `run.json`、`work-order.md`、回执与验收记录 |
| **Worktree 执行根** | `.dispatch/worktrees/<run-id>/` | 一票一 worktree；分支 `dispatch/<run-id>`，默认执行根 |
| **Review ledger 复核账本** | `.dispatch/ledger/reviews.jsonl` | append-only 的有效评审记录，含 review 文件哈希 |
| **Work order 工单** | `work-order.md` | 给执行者的窄上下文：目标、写域、验收、回执契约 |
| **Receipt 回执** | `receipt.json` | 执行者唯一的写入面：做了什么、证据文件在哪 |
| **Verify 验收** | `verify.json` | 独立复跑命令 + diff 写域检查 + 证据哈希 |
| **Review 评审** | `review.json` | 异体评审结论；通过后票据才 `done` |
| **Landing 落地记录** | `.dispatch/runs/<run-id>/landing.json` + `.dispatch/ledger/landings.jsonl` | 把已验证 Run 合入本地 integration branch；不 push、不改目标分支 |
| **Auto 自动化记录** | `.dispatch/runs/<run-id>/auto.json` | 每次自动尝试的执行器退出码、日志哈希、verify 结论，以及可选评审/landing 记录 |
| **Persona 人设** | `tickets/personas/*.md` 或外部角色卡 | 派单员为票据选择的可复用角色；渲染工单时注入紧凑 preamble |

### 状态机

```text
ready ──render──> claimed ──start──> running ──verify(pass/degraded)──> review ──review(pass)──> done
                                      │                              │
                                      └──verify(fail)──> failed      └──review(fail)──> failed
```

- 没有运行记录、但依赖未完成的票据，`status` 显示为 `blocked`。
- `failed` 的运行可以重新 `render`（旧运行记录保留），并会继续出现在 `status` / `export` 的可重试 frontier 中；重新 `render` 后进入新一轮 `claimed`。
- 状态存放在 `.dispatch/state.json`；`run.json` / `verify.json` / `review.json` 是每一次运行的证据链；`reviews.jsonl` 是跨运行的复核账本。
- `done` 之后可以执行 `dispatch land`：把 Run 快照合并到本地 integration branch，写 `landing.json` 与 `landings.jsonl`；目标分支不变，不 push。

---

## 3. 票据格式

一票一文件，文件名建议 `<id>-<slug>.md`：

```markdown
# 01: Create greeting

**What to build:** Write greeting.txt containing hello, with a test.
**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Persona: (unassigned)
- Write scope: greeting.txt
- Write scope: tests/
- Read scope: README.md
- Verify: python -m pytest -q

## Acceptance

- [ ] greeting.txt contains hello.
- [ ] The test passes.
```

规则：

- `# <id>: <title>` 是票据头；id 只允许字母、数字、`.`、`_`、`-`。
- `**Blocked by:**` 写依赖 id，逗号分隔；没有依赖写 `None`。
- `## Dispatch` 下的 `Owner`、`Risk`、`Write scope`、`Verify` 必填；重复的 `Write scope` / `Verify` 会累加。
- `Persona` 可选；写相对票据目录的人设文件路径或短名。`assign` 会复制源文件到 `tickets/personas/` 并写入该行；`lint` 会拒绝解析失败的人设。
- 写域拒绝绝对路径、盘符、`..`、反斜杠；写域是 git 路径的相对前缀或 glob。
- `Verify` 命令按当前平台 shell 执行（Windows 为 `cmd.exe`，其他平台为 `/bin/sh`），支持 `&&`、管道、带引号的参数和 Windows 反斜杠路径。
- 风险等级：`L0` 只读、`L1` worktree、`L2` 沙箱进程、`L3` 宿主/GPU 环境、`L4` 必须人工确认。v0.7 仍按风险控制执行面；DSH 看板兼容层会把风险映射到卡片 permission，唯一强制评审点是 L4 必须 `--human`。
- `## Acceptance` 至少一条 `- [ ]`；验收命令必须能从 execution root 复跑。

---

## 4. 快速开始

前置：Python 3.11+、git；在本仓库根目录执行：

```bash
python -m pip install -e ".[dev]"
dispatch --version
```

> 如果 `dispatch` 不在 PATH，用 `python -m agent_dispatch` 代替，或把 pip 提示的 Scripts 目录加入 PATH。

在一个空目录里走完整流程：

```bash
mkdir dispatch-demo && cd dispatch-demo
git init -q
git config user.email demo@example.com
git config user.name Demo

# 1) 建票
dispatch new 01 \
  --title "Create greeting" \
  --what "Write greeting.txt containing hello, with a test." \
  --write-scope greeting.txt \
  --write-scope tests/ \
  --verify "python -m pytest -q"

# 2) 校验 + 看依赖分波
dispatch lint
dispatch plan

# 3) 先提交票据，保证 render 有 base commit
git add . && git commit -qm "tickets"

# 4) 领取并生成工单
dispatch render 01 --agent worker-a
# 输出：Run ID、Execution root（.dispatch/worktrees/<run-id>）与 Worktree branch；
# 工单在 .dispatch/runs/<run-id>/work-order.md
```

执行者 worker-a 按工单实现，但只写两处：

1. 业务文件：greeting.txt 和 tests/test_greeting.py，写在 **execution root**（worktree）里。
2. 运行目录里的回执：.dispatch/runs/<run-id>/receipt.json。

    {
      "ticket_id": "01",
      "run_id": "01-...",
      "status": "done",
      "summary": "Added greeting.txt and its test.",
      "criteria": [
        {
          "id": 1,
          "verdict": "pass",
          "note": "greeting.txt contains hello",
          "evidence": [
            {"kind": "file", "path": "evidence/greeting.txt"},
            {"kind": "inline", "content": "hello\n"},
            {"kind": "absent", "path": "src/old_greeting.py"},
            {"kind": "command", "command": "python -m pytest -q", "exit_code": 0},
            {"kind": "note", "note": "人工核对过输出"}
          ]
        },
        {
          "id": 2,
          "verdict": "pass",
          "evidence": [{"kind": "file", "path": "evidence/test.log"}]
        }
      ]
    }

同时把证据文件放进同一个运行目录（证据路径必须相对运行目录，不能是绝对路径）：

    .dispatch/runs/<run-id>/evidence/greeting.txt
    .dispatch/runs/<run-id>/evidence/test.log

回执必须给每条 acceptance 一个 criterion，id 正好是 1..N，不能缺、不能多、不能重复。证据类型：

- **file**：文件存在；带 sha256 就核对，不带则记录实际哈希。
- **inline**：字面内容；带 sha256 就核对。
- **absent**：该相对路径必须不存在。
- **command**：执行者报告的命令与退出码；verify 不复跑，但 exit_code 必须为 0。
- **note**：只有人工/agent 陈述；一个 criterion 如果只有 note 证据，会把整体结论降为 degraded。

然后由派单台推进状态：

    dispatch start 01
    dispatch verify 01
    dispatch review 01 --reviewer reviewer-b --verdict pass --notes "Checked independently."
    dispatch status
    dispatch status --json

verify 会做这些检查：

- 票据在 render 之后没有被改过（sha256 对比）。
- receipt.json 存在、JSON 合法、status=done、字段齐全。
- 逐条按当前平台 shell 在 **execution root** 复跑票据里的 Verify 命令，退出码必须为 0；stdout/stderr 存到 logs/ 并算哈希。
- 真实 git diff 的每个文件都落在 Write scope 内；worktree 之外的 **main checkout** 也必须干净。
- 为 execution root 的完整 diff（含未跟踪文件）计算 `diff_hash`，供 `land` 在落地前复核。
- 回执 criteria 覆盖全部 acceptance，并核对证据文件的 sha256 / inline hash / absent 路径。

退出码：0 = passed，2 = degraded（可进入 review 但需显式接受），1 = failed。review 会拒绝实现者自审：评审者不能等于票据的 Owner，也不能等于 render --agent 的领取人；L4 票据必须加 --human；degraded 验收必须加 --accept-degraded。有效评审会追加 .dispatch/ledger/reviews.jsonl。

### 落地为 integration branch（v0.5）

票据通过 `review` 后，可以把它合入本地 integration branch，交给人工开 PR：

```bash
dispatch land 01
dispatch land 01 --into main --branch integration/demo --json
```

- 默认目标分支为 `main`（没有则 `master`，再退回当前分支）；默认 integration branch 为 `dispatch/land/<run-id>`。
- 只创建本地 integration branch，**不 push、不切换、不合并目标分支**；`landing.json` 写到 Run 目录，并追加 `.dispatch/ledger/landings.jsonl`。
- land 要求票据和 Run 都是 `done`、主检出干净、Run 有 worktree、票据内容未变、integration branch 不存在。
- land 会把 worktree 里的未提交改动提交为 run commit；因此应先完成 review 再 land。land 前还会复核 `verify.json` 的 `diff_hash`，review 后 worktree 再被修改会被拒绝，必须重新 verify/review。
- 合并冲突时清理临时 worktree 和 integration branch，目标分支保持原样；成功后从 integration branch 人工开 PR。

### 半自动推进（v0.6）

`dispatch auto` 把 `render → start → 外部执行器 → verify` 串起来。执行器是你提供的 shell 命令，dispatch 不内置 agent 运行时；是否“全自动”取决于你给它的命令，门禁仍由 dispatch 掌握。

```bash
# 默认停在 review：执行器实现 + 自己写回执，dispatch 自动 verify
dispatch auto 01 --executor "python tools/executor.py"

# 失败最多重试 2 次（每次重新执行同一个 worktree）
dispatch auto 01 --executor "python tools/executor.py" --max-attempts 2

# 继续到 land：必须另给独立 reviewer 命令，且 reviewer 写 review-result.json
dispatch auto 01 --executor "python tools/executor.py" \
  --until land --reviewer reviewer-b --reviewer-command "python tools/reviewer.py"
```

执行器和 reviewer 都在 Run 的 worktree 里运行，并收到这些环境变量：

| 变量 | 含义 |
|---|---|
| `DISPATCH_TICKET_ID` / `DISPATCH_RUN_ID` | 当前票据与 Run |
| `DISPATCH_RUN_DIR` | Run 目录；`receipt.json` 与证据必须写在这里 |
| `DISPATCH_EXECUTION_ROOT` | 当前 worktree；业务文件写在这里 |
| `DISPATCH_WORK_ORDER` | 工单路径 |
| `DISPATCH_TICKET_PATH` | 票据路径 |
| `DISPATCH_ATTEMPT` | 第几次尝试，从 1 开始 |
| `DISPATCH_REVIEWER` / `DISPATCH_VERIFY_JSON` / `DISPATCH_REVIEW_RESULT` | 仅 reviewer 命令可见；reviewer 必须把 `{"verdict":"pass"|"fail","notes":"..."}` 写到 `DISPATCH_REVIEW_RESULT` |

- 默认 `--until review`：verify passed（退出码 0）或 degraded（退出码 2）后停在 `review`；degraded 仍需人工 `review --accept-degraded`。
- `--until land`：reviewer 退出码为 0 且 verdict=pass 才会记录评审并调用 `land`；reviewer 不能是 Owner 或领取人。land 仍只建本地 integration branch，不 push、不合并目标分支。
- 执行器的退出码不是验收结论；`verify` 复跑票据命令、检查 diff 与证据，verify 通过才算通过。失败时若还有 `--max-attempts`，Run 会重置为 running 再执行一次；用尽后状态为 `failed`。
- 每次尝试的执行器日志、日志哈希和 verify 结果写到 Run 目录的 `auto/` 与 `auto.json`；reviewer 命令的输出写 `auto/reviewer.log`，不覆盖执行器日志。不会因为自动推进而跳过 review 账本或 land 记录。

当还有 `ready` 票据时（例如刚 `lint` / `plan` 之后），可以导出文件，或交给 DSH 子智能体 / Agent Team。

### 先选人设（v0.7）

```bash
# 搜索可解析的人设；可重复 --search-root
dispatch personas list --search-root <人设目录> --json

# 写入票据 Persona；源文件复制到 tickets/personas/，并记 assignments.jsonl
dispatch assign 01 --persona <文件或短名> --by dispatcher
```

> `assign` 只改 Persona 行，不改写域、验收或依赖；票据已 claimed / running / review / done 时拒绝。

### 两阶段、上下文包与收口（v0.7.1 → v0.8）

```bash
# 1) 只读阶段：生成 brief 模板（理解的目标 / 计划 / 准备改动的文件 / 风险 / 疑问）
dispatch brief 01
dispatch brief 01 --check                 # 非空、非占位才返回 0
dispatch brief 01 --approve 潘杰           # 记 brief 与票据的 sha256；任一被改，审批自动失效

# 2) 实现阶段：没有有效审批直接拒绝开局
dispatch render 01 --agent implementer --require-brief

# 3) 上下文包：票面之外的项目事实（入口文档摘录 / 同票历史运行 / 阻塞邻居 / 踩坑索引）
dispatch context 01
dispatch render 01 --agent implementer --with-context   # 写进 Run 目录并附到 work-order.md

# 4) 收口：检查点 + 票据 / brief / diff 三方对照
dispatch checkpoint 01 --label before-review
dispatch closeout 01
```

> `auto` 重试不再原样重跑：第 n 次尝试前会把第 n-1 次的 `verify_errors` 写成 `auto/feedback-<n-1>.md`，并用环境变量 `DISPATCH_FEEDBACK` 指给执行端。

### 需求对齐（v0.9）

```bash
dispatch align payment-import --level standard   # 写 docs/questions/to-questionnaire-<slug>.md
dispatch spec  payment-import                   # 问卷答满才放行，写 docs/specs/<slug>.md 骨架
dispatch tickets payment-import                  # 按交付标准逐条切草稿票到 .dispatch/drafts/
```

> 这三条只产出骨架与门禁，不代替思考：拷问、选型、规格正文仍由会话完成（ADR-0007 的五段主流程 S1/S3/S4）。

### 导出为文件（只读）

```bash
dispatch export --format agent-team
dispatch export --format codex
dispatch export --format generic
dispatch export --format agent-team --output ready.md
```

> `export` 只读取可执行的 `ready` / `failed` 票据，不调用任何远端 API；票据进入 `claimed` / `running` / `review` / `done` 后不会再出现在导出里。`agent-team` 生成 Team Lead 简报 + 每票工单；旧执行端仍可使用 `dsh-team` JSON。

### DSH 看板兼容层（v0.2 → v0.5，非推荐路径）

以下命令只作兼容保留，不再出现在 `SKILL.md` 主流程；新任务优先使用 `agent-team` 导出或 `render` 单票工单。

前置：DSH Desktop 正在运行，任务看板插件的 Web GUI 可访问。默认地址是 `http://127.0.0.1:50567`；端口不同用 `--url` 或环境变量 `DSH_TASK_BOARD_URL` 覆盖。

```bash
# 先看会创建哪些卡，不联网
dispatch dsh push --dry-run --json

# 创建卡片；push 本身只创建，不运行
dispatch dsh push --project agent-dispatch

# 团队模式：一张 teamRun 父卡 + 每票一张直接子卡
dispatch dsh push --mode team --project agent-dispatch

# 触发已映射卡片运行；触发即返回，不等待终态
dispatch dsh run 01

# 需要指定已有 task id 或重新运行
dispatch dsh run 01 --task-id <task-id> --rerun

# 读回看板状态（本地映射 + 远端任务状态）
dispatch dsh status

# 外部 agent 完成后，把结果回写到映射卡
dispatch dsh outcome 01 --result succeeded --by worker-a --summary "tests and diff checked"

# 修改已映射卡片（不运行）；--patch 可传任意非空 JSON object
dispatch dsh update 01 --title "新标题" --description "补充说明" --prompt "新的提示词"

# 归档或删除已映射卡片
dispatch dsh archive 01
dispatch dsh delete 01
```

- 卡片 id 由 `project` + 票据 id 确定性生成，重复 `push` 不会重复建卡。
- `push` 只创建卡，**不会运行卡**；`dsh run` 才发运行 action。
- `dsh run` 发送 `{kind:"run", taskId}`；`--rerun` 发送 `{kind:"rerun", taskId}`（2026-10-21 已实测：同一卡第二次 execution 成功）。命令触发后立即返回 status/execution id，不等待终态；要等结果请用 `dsh status` 或 DSH GUI。
- `update` 发送 `{kind:"update", taskId, patch}`，`patch` 必须是非空 object；`archive` / `delete` 只发送 `{kind, taskId}`。
- `archive` 只写 `archivedAt`，不删除卡；`delete` 会物理删除。删除有子卡的父卡前，先删除或解除子卡，否则看板返回 `task has subtasks; detach or delete them first`。
- 这三个命令只改看板卡，不改本地票据状态；验收仍走 `dispatch verify` / `dispatch review`。
- 映射写入 `.dispatch/dsh-map.json`，不提交到 Git。
- `dsh outcome` 只是把外部执行结果记到看板执行记录，**不代替** `dispatch verify`；验收仍以本地命令、diff 和证据哈希为准。
- 2026-10-21 实测：显式 POST `{kind:"run", taskId}` 后 Host 实际 spawn teammate，父卡/子卡 status=done、result=succeeded；`dsh run` 封装的就是这个 action，并已用真实看板 probe 卡完成 wrapper e2e（status=done、execution succeeded、summary=DSH_RUN_PROBE_OK，约 32 秒）。2026-10-21 另用真实 probe 卡实测 `--rerun`：同一卡产生两次 execution，均 succeeded，summary 均为 DSH_RERUN_PROBE_OK。证据见 `references/dsh-board.md`。

---

## 5. CLI 一览

| 命令 | 作用 |
|---|---|
| `dispatch new <id> --title ...` | 生成一张可 lint 的票据 |
| `dispatch lint` | 校验所有票据；有错返回非 0 |
| `dispatch plan` | 按依赖算拓扑波次、frontier、写域冲突 |
| `dispatch render <id> --agent <name> [--no-worktree] [--require-brief] [--with-context]` | 创建 Run + worktree + Work order，状态 `claimed`；`--no-worktree` 回退主仓；`--require-brief` 无有效 brief 审批拒绝开局；`--with-context` 把上下文包写进 Run 并附到工单 |
| `dispatch start <id>` | `claimed` → `running` |
| `dispatch verify <id>` | 独立验收；passed/degraded → `review`，failed → `failed`；退出码 0/2/1 |
| `dispatch review <id> --reviewer ... --verdict <pass 或 fail> [--accept-degraded]` | 异体评审；通过 → `done`，并追加 review ledger |
| `dispatch land <id> [--into <目标分支>] [--branch <integration 分支>]` | 把已验证 Run 合入本地 integration branch；目标分支不变，不 push |
| `dispatch auto <id> --executor <shell> [--max-attempts N] [--until review 或 land] [--reviewer ... --reviewer-command ...]` | 半自动推进：render → 外部执行器 → verify（可重试）；`--until land` 需独立 reviewer 命令 |
| `dispatch status [--json]` | 每张票的 effective state、blocked_by、next frontier |
| `dispatch assign <id> --persona <文件或短名> [--by <名字>]` | 为票据选择并写入人设；源文件复制到 `tickets/personas/`，记 `.dispatch/assignments.jsonl` |
| `dispatch personas list/show ...` | 搜索 / 查看可解析的 agent 人设（本地角色卡、agency、GSD、ruflo 等） |
| `dispatch context <id>` | 生成 `.dispatch/context/<id>.md` 上下文包：入口文档摘录、同票历史运行、阻塞邻居、踩坑索引；只读、确定性 |
| `dispatch brief <id> [--check\|--approve <人>]` | 生成 / 校验 / 审批只读 brief（`.dispatch/briefs/<id>.md`）；审批记 brief 与票据的 sha256，任一被改即失效 |
| `dispatch checkpoint <id> [--label <名>] [--list]` | 为 Run 发布不可变检查点（代次目录 + manifest + diff + 恢复说明），原子替换 `current.json` |
| `dispatch closeout <id>` | 票据 / brief 声明文件 / 实际 diff 三方对照，写机器可读收口报告 + 人读页 |
| `dispatch align <slug> [--level quick\|standard\|thorough]` / `spec <slug>` / `tickets <slug>` | 需求问卷（3/6/10 问）→ 问卷答满放行写 spec 骨架 → 按交付标准切草稿票 |
| `dispatch export --format ...` | 导出就绪工作到 agent-team / codex / generic（dsh-team 兼容；只读） |

通用参数：`--tickets` 指定票据目录，`--root` 指定仓库根（默认当前目录）。省略 `--tickets` 时，`render` / `status` / `export` 读取 `<root>/tickets`；`lint` / `plan` / `new` 读取当前目录下的 `tickets`。

---

## 6. 导出格式

| 格式 | 产物 | 用途 |
|---|---|---|
| `agent-team` | Markdown：Team Lead 简报 + 每票 ticket_section（含 Persona） | 交给 DSH Agent Team；Team Lead 先收 brief 再放行实现 |
| `dsh-team` | JSON 数组：`subject` / `description` / `ownerName` / `blockedBy` / `writeScopes` | 兼容旧 DSH `team_task_create`；不再作为技能主路径 |
| `dsh-board` | JSON 文档：`format` / `version` / `endpoint` / `actions` | 兼容旧 DSH 看板；非推荐路径 |
| `codex` | 每票一段 work-order 风格 Markdown | 粘给 Codex 会话 |
| `generic` | 按 id 排序的确定性 Markdown | 任意执行端 / 人工阅读 |

---

## 7. 目录结构

```text
agent-dispatch/
├── src/agent_dispatch/
│   ├── ticket.py      # 解析、lint、依赖边
│   ├── graph.py       # 拓扑分波、frontier、写域冲突
│   ├── workorder.py   # 工单渲染、回执 schema
│   ├── state.py       # state.json、Run 生命周期、git worktree
│   ├── verify.py      # 验收门禁、判据级证据
│   ├── review.py      # 异体评审、review ledger
│   ├── landing.py     # integration branch、landing ledger
│   ├── auto.py        # 外部执行器、重试、可选评审与落地
│   ├── export.py      # status / 文件导出适配器（含 agent-team）
│   ├── persona.py     # 人设解析、发现、注入
│   ├── dsh.py         # DSH 看板兼容层（非技能主路径）
│   └── cli.py         # 命令行入口
├── tests/             # pytest；按票据逐张红→绿
├── tickets/           # 你的票据（一票一文件）
├── .dispatch/         # 运行态：runs、worktrees、ledger、state.json、dsh-map.json（一般不提交）
└── .scratch/          # 本项目的 spec 与实施票据
```

---

## 8. 开发

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

设计边界与后续方向见 `.scratch/agent-dispatch-v0/spec.md`。v0.7 的关键约束仍是：**票据是事实源，运行记录是证据链，状态只能由门禁推进；一票一 worktree；auto 只调用外部命令，不绕过 verify/review；land 只建 integration branch，人工开 PR；Persona 只补充角色上下文，冲突时以票据写域、Acceptance、Verify 为准；DSH 看板只是兼容投递面，不是验收面。**

## 9. 作为技能使用（跨项目）

本仓库不是“只给本项目用的 CLI”。它自带一个可复制的技能层：

```text
SKILL.md                  # 技能入口与触发词
scripts/dispatch.py       # 直接用仓库内 src 运行，不依赖 pip install
scripts/build_skill.py    # 生成干净技能目录
src/agent_dispatch/       # 自带框架
references/               # 票据、Codex 细节
templates/ticket.md       # 最小票据模板（含 Persona 字段）
agents/personas/          # 派单员等人设
agents/openai.yaml        # 技能显示信息
```

生成并安装到其他项目：

```bash
# 1) 生成干净技能包（默认 dist/agent-dispatch-skill）
python scripts/build_skill.py

# 2) 复制到全局技能目录（所有项目可用）
#    Windows PowerShell:
#    Copy-Item -Recurse -Force dist/agent-dispatch-skill "$HOME\.agents\skills\agent-dispatch"
#    Linux/macOS:
#    cp -R dist/agent-dispatch-skill ~/.agents/skills/agent-dispatch

# 3) 从任意项目调用
python "$HOME/.agents/skills/agent-dispatch/scripts/dispatch.py" --version
python "$HOME/.agents/skills/agent-dispatch/scripts/dispatch.py" lint
```

也可以只装到单个项目：把 `dist/agent-dispatch-skill` 复制成 `<项目>/.agents/skills/agent-dispatch`。

要点：

- 技能根目录就是框架根，`src/agent_dispatch` 随技能一起走；目标项目不需要安装 Python 包。
- 目标项目的 `tickets/`、`.dispatch/` 和证据仍写在目标项目根目录，不写进技能目录。
- `tests/test_skill.py` 覆盖了 wrapper 从任意 cwd 启动、构建产物自包含、构建后入口可运行。
