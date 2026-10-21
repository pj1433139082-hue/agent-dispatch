# 派单台 · agent-dispatch

> **ask-matt 决定做什么、先后做什么；dispatch 决定谁做、能写哪、拿什么证据。**

`agent-dispatch` 是一个文件优先的任务编排分发 CLI。它把“票据”变成可执行的工单，把执行者的回执交给独立验收门禁，再交给异体评审，最后才允许票据进入 `done`。

当前版本 **v0.3.0**，Python 3.11+，运行时只用标准库；pytest 仅用于本项目开发测试。v0.2 新增 DSH 任务看板的真实推送、状态回读与外部结果回写；v0.2.1 修复跨项目 `--root` 路径解析、Windows `Verify` 命令执行和失败票据的重试可见性；v0.3 新增看板卡片的 update / archive / delete。

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
- `verify` 复跑票据里的验收命令，检查真实 git diff 是否越出写域，并给证据算哈希。
- `review` 要求评审者不是票据 owner，也不是实际领取人；L4 风险必须显式 `--human`。

v0.3 仍刻意不做：Web UI、多用户权限、云沙箱、自动合并、自动替代 DSH / Codex。它只做“票据 → 工单 → 回执 → 验收 → 评审 → 状态/导出/投递”这条最小闭环。

---

## 2. 核心对象

| 对象 | 存在形式 | 作用 |
|---|---|---|
| **Ticket 票据** | `tickets/<id>-<slug>.md` | 需求、依赖、写域、验收命令的唯一事实源 |
| **Run 运行** | `.dispatch/runs/<run-id>/` | 一次领取；包含 `run.json`、`work-order.md`、回执与验收记录 |
| **Work order 工单** | `work-order.md` | 给执行者的窄上下文：目标、写域、验收、回执契约 |
| **Receipt 回执** | `receipt.json` | 执行者唯一的写入面：做了什么、证据文件在哪 |
| **Verify 验收** | `verify.json` | 独立复跑命令 + diff 写域检查 + 证据哈希 |
| **Review 评审** | `review.json` | 异体评审结论；通过后票据才 `done` |

### 状态机

```text
ready ──render──> claimed ──start──> running ──verify(pass)──> review ──review(pass)──> done
                                      │                         │
                                      └──verify(fail)──> failed └──review(fail)──> failed
```

- 没有运行记录、但依赖未完成的票据，`status` 显示为 `blocked`。
- `failed` 的运行可以重新 `render`（旧运行记录保留），并会继续出现在 `status` / `export` 的可重试 frontier 中；重新 `render` 后进入新一轮 `claimed`。
- 状态存放在 `.dispatch/state.json`；`run.json` / `verify.json` / `review.json` 是每一次运行的证据链。

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
- 写域拒绝绝对路径、盘符、`..`、反斜杠；写域是 git 路径的相对前缀或 glob。
- `Verify` 命令按当前平台 shell 执行（Windows 为 `cmd.exe`，其他平台为 `/bin/sh`），支持 `&&`、管道、带引号的参数和 Windows 反斜杠路径。
- 风险等级：`L0` 只读、`L1` worktree、`L2` 沙箱进程、`L3` 宿主/GPU 环境、`L4` 必须人工确认。v0.2 把风险映射到 DSH 卡片 permission；唯一强制评审点是 L4 必须 `--human`。
- `## Acceptance` 至少一条 `- [ ]`；验收命令必须能从仓库根目录复跑。

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
# 输出：Run ID: 01-...；工单在 .dispatch/runs/<run-id>/work-order.md
```

执行者 `worker-a` 按工单实现，但只写两处：

1. 业务文件：`greeting.txt` 和 `tests/test_greeting.py`
2. 运行目录里的回执：`.dispatch/runs/<run-id>/receipt.json`

```json
{
  "ticket_id": "01",
  "run_id": "01-...",
  "status": "done",
  "summary": "Added greeting.txt and its test.",
  "evidence": ["evidence.txt"]
}
```

同时把证据文件放进同一个运行目录（证据路径必须相对运行目录，不能是绝对路径）：

```text
.dispatch/runs/<run-id>/evidence.txt
```

然后由派单台推进状态：

```bash
dispatch start 01
dispatch verify 01
dispatch review 01 --reviewer reviewer-b --verdict pass --notes "Checked independently."
dispatch status
dispatch status --json
```

`verify` 会做这些检查：

- 票据在 `render` 之后没有被改过（sha256 对比）。
- `receipt.json` 存在、JSON 合法、字段齐全。
- 逐条按当前平台 shell 复跑票据里的 `Verify` 命令，退出码必须为 0；stdout/stderr 存到 `logs/` 并算哈希。
- 真实 git diff 的每个文件都落在 `Write scope` 内。
- 回执里的证据文件存在，并记录 sha256。

`review` 会拒绝实现者自审：评审者不能等于票据的 `Owner`，也不能等于 `render --agent` 的领取人；L4 票据必须加 `--human`。

当还有 `ready` 票据时（例如刚 `lint` / `plan` 之后），可以选择导出文件，或直接投递到本机 DSH 任务看板。

### 导出为文件（只读）

```bash
dispatch export --format dsh-team
dispatch export --format dsh-board
dispatch export --format codex
dispatch export --format generic
dispatch export --format dsh-team --output ready.json
```

> `export` 只读取可执行的 `ready` / `failed` 票据，不调用任何远端 API；票据进入 `claimed` / `running` / `review` / `done` 后不会再出现在导出里。拿到 JSON/Markdown 后可以粘到 DSH、Codex 或别的执行端。

### 直接投递到 DSH 任务看板（v0.2 → v0.3）

前置：DSH Desktop 正在运行，任务看板插件的 Web GUI 可访问。默认地址是 `http://127.0.0.1:50567`；端口不同用 `--url` 或环境变量 `DSH_TASK_BOARD_URL` 覆盖。

```bash
# 先看会创建哪些卡，不联网
dispatch dsh push --dry-run --json

# 创建卡片；只创建，不运行
dispatch dsh push --project agent-dispatch

# 团队模式：一张 teamRun 父卡 + 每票一张直接子卡
dispatch dsh push --mode team --project agent-dispatch

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
- `push` 只创建卡，**不会运行卡**；运行仍需在 DSH 看板里由人确认。
- `update` 发送 `{kind:"update", taskId, patch}`，`patch` 必须是非空 object；`archive` / `delete` 只发送 `{kind, taskId}`。
- `archive` 只写 `archivedAt`，不删除卡；`delete` 会物理删除。删除有子卡的父卡前，先删除或解除子卡，否则看板返回 `task has subtasks; detach or delete them first`。
- 这三个命令只改看板卡，不改本地票据状态；验收仍走 `dispatch verify` / `dispatch review`。
- 映射写入 `.dispatch/dsh-map.json`，不提交到 Git。
- `dsh outcome` 只是把外部执行结果记到看板执行记录，**不代替** `dispatch verify`；验收仍以本地命令、diff 和证据哈希为准。
- 2026-10-21 实测：人工触发一张 `teamRun` 卡后，Host 实际启动 Lead + teammate，父卡摘要回传子任务结果；`dispatch` 本身仍只建卡，不自动运行。证据见 `docs/verification/2026-10-21-v0.2-boundaries.md`。

---

## 5. CLI 一览

| 命令 | 作用 |
|---|---|
| `dispatch new <id> --title ...` | 生成一张可 lint 的票据 |
| `dispatch lint` | 校验所有票据；有错返回非 0 |
| `dispatch plan` | 按依赖算拓扑波次、frontier、写域冲突 |
| `dispatch render <id> --agent <name>` | 创建 Run + Work order，状态 `claimed` |
| `dispatch start <id>` | `claimed` → `running` |
| `dispatch verify <id>` | 独立验收；通过 → `review`，失败 → `failed` |
| `dispatch review <id> --reviewer ... --verdict <pass 或 fail>` | 异体评审；通过 → `done` |
| `dispatch status [--json]` | 每张票的 effective state、blocked_by、next frontier |
| `dispatch export --format ...` | 导出就绪工作到 DSH team / DSH board / Codex / generic（只读） |
| `dispatch dsh push [--mode <cards 或 team>] [--dry-run]` | 把就绪票据投递到本机 DSH 任务看板；只建卡不运行 |
| `dispatch dsh status` | 读回 DSH 看板状态并与本地映射对照 |
| `dispatch dsh update <id> [--title/--description/--prompt/--patch JSON]` | 修改已映射卡片；不运行 |
| `dispatch dsh archive <id>` | 归档已映射卡片；不删除 |
| `dispatch dsh delete <id>` | 删除已映射卡片；有子卡先处理子卡 |
| `dispatch dsh outcome <id> --result ... --by ...` | 把外部 agent 的结果回写到映射卡 |

通用参数：`--tickets` 指定票据目录，`--root` 指定仓库根（默认当前目录）。省略 `--tickets` 时，`render` / `status` / `export` / `dsh push` 读取 `<root>/tickets`；`lint` / `plan` / `new` 读取当前目录下的 `tickets`。

---

## 6. 导出格式

| 格式 | 产物 | 用途 |
|---|---|---|
| `dsh-team` | JSON 数组：`subject` / `description` / `ownerName` / `blockedBy` / `writeScopes` | 投给 DSH `team_task_create` |
| `dsh-board` | JSON 文档：`format` / `version` / `endpoint` / `actions`；每个 action 是 DSH 看板的 `create` 信封 | 可由 `dsh push` 直接投递，也可人工检查 |
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
│   ├── state.py       # state.json、Run 生命周期
│   ├── verify.py      # 验收门禁
│   ├── review.py      # 异体评审
│   ├── export.py      # status / 文件导出适配器
│   ├── dsh.py         # DSH 看板投递、回读、外部结果回写、卡片变更
│   └── cli.py         # 命令行入口
├── tests/             # pytest；按票据逐张红→绿
├── tickets/           # 你的票据（一票一文件）
├── .dispatch/         # 运行态：runs、state.json、dsh-map.json（一般不提交）
└── .scratch/          # 本项目的 spec 与实施票据
```

---

## 8. 开发

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

设计边界与后续方向见 `.scratch/agent-dispatch-v0/spec.md`。v0.3 的关键约束仍是：**票据是事实源，运行记录是证据链，状态只能由门禁推进；DSH 看板只是投递与回读面，不是验收面。**

## 9. 作为技能使用（跨项目）

本仓库不是“只给本项目用的 CLI”。它自带一个可复制的技能层：

```text
SKILL.md                  # 技能入口与触发词
scripts/dispatch.py       # 直接用仓库内 src 运行，不依赖 pip install
scripts/build_skill.py    # 生成干净技能目录
src/agent_dispatch/       # 自带框架
references/               # 票据、DSH、Codex 细节
templates/ticket.md       # 最小票据模板
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
