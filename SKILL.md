---
name: agent-dispatch
description: 用票据契约、依赖分波、一票一 worktree、判据级证据、独立验收和异体评审，把任务派给 DSH 子智能体、Agent Team、Codex 或人工执行端。适用于多智能体任务编排、跨项目派单，以及把 ask-matt 产出的票据变成可执行工单。触发词：派单、任务编排、agent dispatch、票据、工单、依赖分波、写域、验收门禁、子智能体、Agent Team、Codex 工单。
---

# agent-dispatch · 票据派单台

本技能把“谁做、在哪个 worktree 做、能写哪、拿什么证据、谁来验收”变成可执行的文件契约。它自带一个零第三方依赖的 Python 框架（`src/agent_dispatch`），不要求目标项目安装 `dispatch`，也不依赖全局 PATH。当前版本 0.50.0。

## 何时使用

- 一个任务要拆成多张有依赖关系的票据，分给多个 agent 或人。
- 需要限制每个执行者的写作用域，防止越界改动。
- 需要一票一 worktree、独立复跑验证命令、检查真实 git diff、按 acceptance 逐条收证据。
- 需要异体评审，避免实现者自己宣布完成。
- 需要给每张票指定 agent 人设，并由派单员写入后再分发。
- 需要把 ready 票据交给 DSH 子智能体或 Agent Team，或导出成 Codex 工单。
- 需要半自动推进：用 `auto` 调用外部执行器并自动跑 verify，可配置失败重试与独立评审。

## 何时不用

- 单文件、一步就能完成的小改动：直接用目标项目的测试/评审流程即可。
- 只需要讨论方案、还没有可执行任务：先用 `grill-with-docs` 或 `to-tickets`。
- 需要替代 DSH Agent Teams、Codex 或 CI：本技能只做票据、工单、门禁与投递，不做执行器；`auto` 只调用你提供的外部命令，不内置模型运行时。

## 自带框架

技能根目录就是框架根。调用入口是：

```bash
python <技能目录>/scripts/dispatch.py --help
```

`scripts/dispatch.py` 会优先把技能目录下的 `src` 放入 `sys.path`，再调用 `agent_dispatch.cli`。因此：

- 复制整个技能目录到 `~/.agents/skills/agent-dispatch` 或 `<项目>/.agents/skills/agent-dispatch` 即可使用。
- 不需要先 `pip install`，也不会误用系统里的另一个 `agent_dispatch` 包。
- 目标项目的票据、运行态和证据仍写在目标项目根目录，不写进技能目录。

## 冷启动（30 秒）

在目标项目根目录执行：

```bash
# 1) 确认框架可运行
python <技能目录>/scripts/dispatch.py --version
python <技能目录>/scripts/dispatch.py --help

# 2) 建票或检查已有票据
python <技能目录>/scripts/dispatch.py lint
python <技能目录>/scripts/dispatch.py plan

# 3) 看当前 frontier
python <技能目录>/scripts/dispatch.py status --json
```

如果目标项目还没有 `tickets/`，先复制 `templates/ticket.md` 或运行：

```bash
python <技能目录>/scripts/dispatch.py new 01 \
  --title "Create greeting" \
  --what "Write greeting.txt containing hello, with a test." \
  --write-scope greeting.txt \
  --write-scope tests/ \
  --verify "python -m pytest -q"
```

## 流程地图（四条）

| 流程 | 什么时候用 | 命令链 |
|---|---|---|
| **A 需求→票** | 模糊需求要变成可执行票 | `align → select → sign → spec → confirm → tickets → lint → stage` |
| **B 单票执行** | 已有票，要真的做完一件事 | `brief → render → handoff → start → verify → review → land`（可选 `closeout`） |
| **C 批量/自动** | 想半自动推进或整波落地 | `auto <id> --executor …` / `land --wave` |
| **D 运维恢复** | 状态不对、卡住、要体检 | `doctor [--fix] / sweep / repair / claim / release / gc / retry` |

完整版（谁产出谁消费、与其它技能的交界）：`docs/flows.md`。

## 主流程

0. **brief 是模板，不是一次生成就能批**：`dispatch brief <id>` 产出五段（理解/计划/要改的文件/风险/疑问），**必须把五段 `<填写：…>` 改成正文**再 `brief <id> --approve <人>`；占位内容会被拒。

1. **建票**：一张票一个 Markdown 文件，写清 `What to build`、`Blocked by`、`Owner`、`Risk`、`Persona`、`Write scope`、`Verify`、`Acceptance`。需要人设时先用 `personas list --search-root <目录>` 搜索，再用 `assign <id> --persona <文件或短名>` 写入；派单员只改 Persona，不改票据契约。
2. **校验与分波**：`lint` 拒绝缺字段、自依赖、环、未知依赖；`plan` 输出拓扑波次、frontier 和同波写域冲突。
3. **派发**：
   - 本地执行：`render <id> --agent <name>` 创建 Run、独立 git worktree（分支 `dispatch/<run-id>`）和 `work-order.md`，票据进入 `claimed`。`--no-worktree` 仅作逃生口。
   - DSH 子智能体 / Agent Team：单票用 `render <id> --agent <name>` 生成 `work-order.md`，交给一个子智能体；多票用 `export --format agent-team` 生成 Team Lead 简报和每票工单。Team Lead 必须先收 brief，再放行实现。
   - Codex：`export --format codex` 生成工单，交给 Codex 会话。
   - 半自动：`auto <id> --executor <shell>` 自动完成 render → 执行器 → verify；失败可 `--max-attempts` 重试。`--until land` 还必须提供独立 `--reviewer` 与 `--reviewer-command`。
   - **先 brief 再动手（v0.7.1）**：`brief <id>` 生成只读 brief（理解 / 计划 / 要改的文件 / 风险 / 疑问）→ 人审 → `brief <id> --approve <人>`；之后 `render <id> --require-brief` 才放行实现。票据或 brief 在审批后被改动，审批自动失效。
4. **执行者只写两处**：在 **execution root**（worktree）写业务文件；在运行目录写 `receipt.json` 和证据文件；**不能改票据状态**。
5. **独立验收**：`start` → `verify`。`verify` 在 execution root 复跑票据命令，按 acceptance 逐条核对 `criteria` 证据，检查 worktree 与主仓都没有越界改动。结论分 `passed` / `degraded` / `failed`，退出码 0 / 2 / 1。
6. **异体评审**：`review --reviewer <另一个名字> --verdict pass`；通过才进入 `done`。L4 必须加 `--human`；degraded 验收必须加 `--accept-degraded`。
7. **落地**：`land` 要求**主检出干净**（脏文件会逐个列出；`setup` 会写 `.gitignore` 排除 `.dispatch/`，但 `tickets/` 里新生成的票仍需先提交），然后 `land <id>` 把已验证 Run 合入本地 integration branch（默认 `dispatch/land/<run-id>`），只创建分支并写 landing 记录；不 push、不合并目标分支。land 会复核 verify 的 worktree diff hash，review 后改动会被拒绝。

## 选型角色（v0.10.0）

S2 的角色是**必须有**的，不是可选的：

| 角色 id | 必须 | 产出 | 证据门槛 |
|---|---|---|---|
| `oss-scout` | 是 | `01-oss.md` | ≥2 个开源参照，指到具体文件:函数或提交哈希，并写明不采用的理由 |
| `search-scout` | 是 | `02-sources.md` | 每条事实附 URL + 原文摘录 + 抓取日期 + 版本号；查不到写「未证实」 |
| `adversary` | 是 | `03-adversary.md` | 列出方案没写出来的假设，每条给一个可证伪的最小实验或反例（≤7 条） |
| `domain-owner` | 否（`--with`） | `04-domain.md` | 硬约束逐条，标「绝对不行 / 代价高但可行」，给最小可行落点 |
| `cost-keeper` | 否（`--with`） | `05-cost.md` | 依赖与体积（gzip）、运行开销、维护活跃度，全部给数字 |
| 自定义 | `--add id:persona` | `9N-<id>.md` | 按自带 persona 的判据 |

人设文件随技能分发（`agents/personas/`），用 `personas list` 可查；`--add` 可以挂你自己的角色卡。汇总表 `99-summary.md` 留了**甲方签字行**——按 ADR-0007 Q1，选型结论必须你签。

## 上下文包、两阶段与收口（v0.8.0）

新会话只拿到票面就会跑偏。两个补丁：

- `context <id>` → `.dispatch/context/<id>.md`：票面框架、目标、写/读域、完成定义、**项目入口文档摘录**（AGENTS.md / CLAUDE.md / CONTEXT.md）、**同票历史运行**（state / verify / error）、**阻塞邻居**、**踩坑笔记索引**。只读、确定性、不调模型。`render --with-context` 会把它写进 run 目录并附到 `work-order.md`。
- `brief <id>` → `.dispatch/briefs/<id>.md`：只读阶段的五段式 brief；`--check` 校验非空非占位，`--approve <人>` 记录审批（brief 与票据的 sha256 一起记），`render --require-brief` 无有效审批直接拒绝开局。
- `auto` 重试不再原样重跑：第 n 次尝试前把第 n-1 次的 `verify_errors` 写成 `auto/feedback-<n-1>.md`，并用环境变量 `DISPATCH_FEEDBACK` 指给执行端。

- `checkpoint <id>` → `<run>/checkpoints/<NNN>-<label>/`：`checkpoint.json`（逐文件 sha256 + diff_hash + parent）、`diff.patch`、`status.txt`、`restore.md`；发布后 `current.json` 原子切换，代际只追加不覆盖。
- `closeout <id>` → `<run>/closeout.json` + `closeout.md`：verify 状态、receipt criteria 与票面 acceptance 的条数对应、越出写域的改动、brief 声明却没改 / 没声明却改了；不过就列出 findings。`land --require-closeout` 会在 closeout 不是 pass 时拒绝落地。

## 发布前验收

```bash
python scripts/acceptance.py          # 人读
python scripts/acceptance.py --json   # 机读（CI）
```

两条真机路径：**A** auto `--protocol full --until land` 全链路；**B** 老项目升级回归（无 `skill_version`/`deadline_seconds` 的旧 run 不许崩、不许迁移数据）。退出码 0 = 都过。

## 门必须先问再签（v0.21.0）

S1 / S2 / S3 三个门**不许由 agent 代拍板**。固定动作：

1. `dispatch stage <slug> --prompt` 拿到结构化问题（`{id, header, question, options[{label, description}]}`）；
2. 把这份 JSON **原样**喂给 `ask_user_question`（弹窗）或文字决策卡（弹窗不可用时）；
3. 拿到答案后再落盘：问卷写进 `docs/questions/<slug>.md`、S2 签字用 `dispatch sign <slug> --by <人> --via dialog|card`、S3 规格核对用 `dispatch confirm <slug> --by <人> --via dialog|card`；没确认过 `tickets` 会拒绝拆票。

没有 `--via` 的签字直接报错——审计时能分清"问过的"和"自己写的"。

## auto 一票一停（别把整波塞进一个上下文）

ADR-0010 里 `auto` 是**单票推进器**，不是批量编排器。2026-10-22 水质会话实测：一个上下文里连着跑 `dispatch auto`，跑到第 10 张票时上下文约 **5.4M tokens**，直接 `prompt_too_long` 断掉，票停在半路。

规则：

0. `auto` 开跑前会先做一次体检；索引和磁盘不一致就拒绝（`--force` 才跳过）——先 `dispatch doctor --fix` 再跑。
1. **一次只推一张票**；要推进多张，用 `land --wave` 那份拓扑序，逐票开新会话或在每票之间压缩上下文。
2. `--until` 是**停止点**，不是"继续往下跑到完"。
3. 票失败时先 `dispatch retry <id> --reason …` 再重跑，不要手改 `.dispatch/state.json`（那会造出 EVIDENCE-MISMATCH）。

## 执行端：三条真实路径（dispatch 不创建 agent）

`dispatch` 只做**契约与证据**；谁真的动手，由会话决定。现有三条路，选哪条取决于会话里有什么：

1. **teammate（harness 的 spawn provider）**
   `dispatch handoff <id> --to <agent>` 打出交接内容 → 你用 `send_message` 发过去 → 它交 brief → 批准 → 在 worktree 执行 → `dispatch verify` → **另一个** reviewer 跑 `dispatch review`。
   ⚠️ `render --agent X` 只是把名字写进工作单，**不会创建 teammate**。`list_agents` 里没有这个 target 就发不出去——这时别假装派了。
2. **DSH 看板**
   `dsh push --project <p>` 建卡 → 人在板上点 run（或 `dsh run <id>`）→ 结果用 `dsh outcome` 回写。看板在 `127.0.0.1:62407`（不是 50567），且请求要带 `sec-fetch-site: same-origin`。
3. **外部执行器命令**
   `auto <id> --executor "<cmd>"`。没有 teammate、没接看板时，这条路等同**主代理自己执行**——要如实说明，不要包装成"已派给子智能体"。

## 看板派单必须绑 workspace

`dsh push` **必须**给 `--workspace <id>`：卡片在**那个 workspace** 里跑，不在你当前仓库。省略会在板上默认 workspace 执行——实测把 `hello.txt` 写进了另一个项目。
确需默认 workspace 时显式加 `--allow-default-workspace`。

## 常见误解（来自看板新会话的真机验收）

1. **receipt 的 `file` 证据**：路径可以相对 **run 目录**，也可以相对 **worktree（execution root）**——先在 run 目录找，找不到再去 worktree 找。业务产物天然在 worktree，不必复制。
2. **verify 是命令门，Acceptance 是验收门**：命令只证明"能跑通"，不代表验收项成立。review 要对 Acceptance 逐条签字；票面写的 Verify 弱于 Acceptance 时，以 Acceptance 为准。
3. **brief 门默认是开的**：`setup` 会写 `require_brief: true`，之后 `render` 自动校验审批；不想要就改配置。老项目没配置时行为不变（需显式 `--require-brief`）。
4. **land 与 review-packet**：`review` 通过时会自动快照一份 packet，所以 `land` 通常直接过；`review-packet` 命令用于手动补/分享，`--no-require-packet` 只给老 run 迁移用。
5. **票面的 `**Status:**` 只是作者标记**：真实状态看 `dispatch status` / `.dispatch/state.json`，工具不会回写票面。

### 身份：名字不等于执行者（有硬门，分三层）

`--agent` 只是写进工作单的声明；`--reviewer` 有**三层硬门**（ADR-0008 D5 + v0.50）：

| 层 | 规则 | 触发条件 |
|---|---|---|
| 1. 名字 | `reviewer` 等于票的 `Owner` 或 run 的 `claimed_by` → **拒绝** | 所有等级 |
| 2. 自审 | L0/L1 可 `--self-reviewed` 显式留痕放行；**L2+ 一律不许** | reviewer 与执行者同名时 |
| 3. 读包证明 | **L2+ 必须 `--packet-hash <review-packet.md 的 sha256>`**，哈希不符即拒；通过后 `packet_attested=true` | L2/L3/L4 |

- L4 还要 `--human`（人工评审）。
- 这三层挡的是"手滑"和"没读包"，**挡不住"同一个模型换个名字"**——要那样得靠会话隔离（`list_agents` 里真有第二个 agent）。
- 没 teammate 时 `render --agent X` 只是标签；交付说明里要写"主代理自执行"。

### brief 门是否强制：看配置，命令自己会说

- `dispatch setup` 默认写 `require_brief: true`；老项目没有这条配置时行为不变（不强制）。
- 强制时 `render` 会打印 `Brief gate: brief 已由 <人> 于 <时间> 审核`；被拦时打印 `brief gate ON, …` 并说明缺什么。
- 想临时强制/绕过：`render --require-brief`（加严）；配置文件改成 `false` 才放行。

### review-packet 与 land 的边界

| 场景 | packet 谁生成 | land 会不会过 |
|---|---|---|
| `review`（手审） | **review 通过时自动快照一份** `review-packet.md/.json` | 过（文件已存在） |
| `auto --until land` | 评审**之前**先生成，并把 `DISPATCH_REVIEW_PACKET` 交给 reviewer | 过；reviewer 回填了错 `packet_hash` 则 `review-invalid` |
| 老 run（没有 packet） | 需要手动 `review-packet <id>` | 不过，除非 `--no-require-packet`（迁移用） |

- `--no-require-packet`：**跳过"有没有包"**的检查（迁移逃生口）。
- `--require-attestation`：更严，要求 reviewer **回填过正确的 `packet_hash`**；手审（review）默认 `packet_attested=false`，会被它挡住。

## 命令速查

| 命令 | 用途 |
|---|---|
| `setup [--tickets 目录] [--executor-mode teammate\|dsh\|command] [--default-reviewer 名字]` | 写 `.dispatch/config.json` + `.gitignore(.dispatch/)`；`default_reviewer` 只在 `review` 没传 `--reviewer` 时生效；幂等 |
| `handoff <id> [--to <agent>] [--json]` | 打印"该发给谁、发什么"的交接内容（工作单路径、执行根、分支、回执位置） |
| `doctor [--json] [--fix]` | 只读体检：票能否 lint、索引与磁盘是否一致、失败票、超期 run、活跃租约；`--fix` 只做安全修复（重建索引 + 删过期租约）；有问题 exit 1 |
| `release <id> [--json]` | 释放该票的文件租约（卡住的 run 用它放锁；幂等，没租约也成功） |
| `retry <id> [--reason …]` | 把 `failed` 的票拉回 `running` 再验一次；旧的 verify/review/closeout 归档到 `attempts/`，索引里留 history |
| `confirm <slug> --by <人> --via <dialog 或 card> [--note …]` | 把 S3「规格已核对」写进 `docs/specs/<slug>.md` 的 `## Confirmation`；`tickets` 未确认前拒绝拆票（`--force` 跳过） |
| `sign <slug> --by <人> --via <dialog 或 card> [--hold 或 --reject]` | 把甲方签字写回 `99-summary.md`（签字人 + 勾选 + 确认方式）；**`--via` 必填**，不写来源不许签 |
| `stage <slug> [--json] [--prompt]` | S1–S5 一屏状态；`--prompt` 输出该阶段要人回答的问题（喂弹窗/决策卡）：问卷 / 选型 / 签字 / 规格 / 票；`next` 指下一步，未就绪 exit 1 |
| `claim <id> [--ttl-minutes 15]` | 把票的写域展开成**文件租约**（`.dispatch/locks/`）：被别的活租约占着就 exit 3，不让两个 run 同时写同一文件 |
| `gc [--apply]` | 回收 ended run 的 worktree：干净且已 land → REMOVE；有未提交改动或未 land → HOLD |
| `seat [--cap 8] [--occupied N] [--inactive a,b]` | 派单前查名额：占用/上限/可回收 inactive，给出可/需回收/阻塞 |
| `review-packet <id>` | 冻结票据、diff、回执与验收证据成评审包；`hashes.diff` 与 `verify.diff_hash` **同源同值** |
| `dsh <push/status/outcome/update/archive/run/delete>` | 投递与看板联动（可选路径，不是默认执行端） |
| `lint` | 校验票据；有错非零退出 |
| `plan` | 拓扑波次、frontier、写域冲突 |
| `status [--json]` | 每张票的有效状态 |
| `new <id> ...` | 生成一张可 lint 的票据 |
| `render <id> --agent <name> [--no-worktree] [--deadline-minutes 15]` | 创建 Run、worktree 和 work-order（记 `skill_version` 与 `deadline_seconds`），状态进入 claimed |
| `start <id>` | claimed → running |
| `verify <id>` | 独立验收；passed/degraded → review，failed → failed；退出码 0/2/1 |
| `review <id> --reviewer ... --verdict <pass 或 fail> [--accept-degraded] [--self-reviewed]` | 异体评审；通过 → done，并追加 review ledger |
| `land <id> \| --wave [--into 目标分支] [--branch 前缀] [--require-closeout] [--require-attestation] [--no-require-packet] [--continue-on-error]` | 把已验证 Run 合入本地 integration branch；**默认要求 review-packet.md 存在**；目标分支不变，不 push |
| `auto <id> --executor <shell> [--max-attempts N] [--until review 或 land] [--reviewer ... --reviewer-command ...]` | 半自动推进：render → 执行器 → verify（可重试）；`--until land` 需独立 reviewer 命令 |
| `auto <id> --executor <shell> --protocol full [--env-hint "<命令>"] [--require-brief]` | 带协议跑：注入 context + 环境前置、检查 brief 门、每次 verify 后发 checkpoint、跑 closeout；`--until land` 必须 closeout pass 才 land |
| `assign <id> --persona <文件或短名> [--by <名字>]` | 把可解析的人设写入票据 Persona；源文件复制到 `tickets/personas/`，并记 `.dispatch/assignments.jsonl` |
| `personas list [--search-root <目录>] [--json]` | 搜索可解析的 agent 人设（本地角色卡、agency、GSD、ruflo 等） |
| `personas show <文件或短名> [--json]` | 读取单个 persona 的身份、能力与提示词 |
| `export --format <agent-team / dsh-team / codex / generic>` | 只读导出；`agent-team` 生成 Team Lead 简报 + 每票工单 |
| `context <id> [--json]` | 生成 `.dispatch/context/<id>.md`：入口文档摘录 / 同票历史运行 / 阻塞邻居 / 踩坑索引 |
| `brief <id> [--check 或 --approve <人>]` | 两阶段：只读 brief 模板、校验五段非空、记录审批（票据与 brief 双哈希） |
| `checkpoint <id> [--label <名>] [--list]` | 发布不可变检查点（manifest + diff.patch + status + restore.md），`--list` 看代际 |
| `select <slug> [--with 角色1,角色2] [--add ID[:PERSONA]] [--list]` | S2：出选型证据包 `docs/selection/<slug>/`——三角色必选（开源借鉴 / 搜索取证 / 对抗审查），可选领域约束与成本守护，其余角色可自带 persona 追加 |
| `sweep [--json]` | 只读巡检：每条 active run 的 `age_seconds / last_artifact / idle_seconds / has_receipt / deadline_seconds / over_deadline`；**不自动 kill** |
| `repair [--write] [--json]` | 从 `.dispatch/runs/*/run.json` 反向重建 `state.json`；默认 dry-run；冲突票**不写**并 exit 1 |
| `align <slug> [--level quick 或 standard 或 thorough]` | S1：出需求问卷 `docs/questions/<slug>.md`，第一段就是档位选择（3 / 6 / 10 问） |
| `closeout <id> [--json]` | 对照 票面 / brief / diff 出收口报告；`land --require-closeout` 才强制 |
| `spec <slug> [--force]` | S3：问卷答满 **且 S2 已签字** 才允许写规格骨架（--force 跳过签字门） `docs/specs/<slug>.md`（Problem / Solution / Stories / Delivery standard / Decisions / Testing / Out of scope） |
| `tickets <slug>` | S4：按规格的 `## Delivery standard` 逐条生成草稿票到 `.dispatch/drafts/<slug>/`，补 Write scope 与 Verify 后进 `tickets/` || `closeout <id> [--json]` | 对照票面 / brief / diff 出收口报告；`land --require-closeout` 才强制 |

通用参数：`--tickets` 指定票据目录，`--root` 指定仓库根（默认当前目录）。省略 `--tickets` 时，`render` / `status` / `export` 读取 `<root>/tickets`；`lint` / `plan` / `new` 读取当前目录下的 `tickets`。

## 票据最小模板

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
- `Blocked by` 写依赖 id，逗号分隔；没有依赖写 `None`。
- 写域拒绝绝对路径、盘符、`..`、反斜杠；写域是 git 路径的相对前缀或 glob。
- 风险：`L0` 只读、`L1` worktree、`L2` 沙箱进程、`L3` 宿主/GPU、`L4` 人工确认。
- `Owner`、`Risk`、`Write scope`、`Verify` 必填；`Acceptance` 至少一条 checkbox。
- `Verify` 必须能从 execution root 复跑；命令按当前平台 shell 执行（Windows `cmd.exe`，其他 `/bin/sh`），支持 `&&`、管道和带引号的参数。

## auto 的协议开关（v0.11.0）

`--protocol full` 把 ADR-0010 的四件挂到 auto 上；默认 `none` 保持旧行为。组合真值表：

| `--protocol` | `--require-brief` | `--until` | 行为 |
|---|---|---|---|
| none | 任意 | review | 旧行为：执行 → verify → 停 review |
| none | 任意 | land | 旧行为：执行 → verify → 评审 → land（**不跑 closeout**） |
| full | 否 | review | 注入 context/env → 执行 → verify → checkpoint → closeout → 停 review |
| full | 是 | review | 同上，但**没审批过的 brief 就不开跑** |
| full | 否/是 | land | 同上，且 **closeout 必须 pass 才 land**，否则 `closeout-failed` |

失败语义：closeout 不过 → `status=closeout-failed`，findings 写进 `auto/feedback-<n>.md` **不自动重跑**（由人或下一张票决定）。

`--until land` 还会先生成 `review-packet.md` 并把 `DISPATCH_REVIEW_PACKET` 交给 reviewer；reviewer 回执里的 `packet_hash` 与实际包**不一致** → `review-invalid`，不 land。

## 半自动推进（v0.6）

```bash
# 默认停在 review（执行器负责写 receipt.json 与证据）
python <技能目录>/scripts/dispatch.py auto 01 --executor "python tools/executor.py"

# 失败最多重试 2 次
python <技能目录>/scripts/dispatch.py auto 01 --executor "python tools/executor.py" --max-attempts 2

# 独立 reviewer 通过后继续 land（只建本地 integration branch）
python <技能目录>/scripts/dispatch.py auto 01 --executor "python tools/executor.py" \
  --until land --reviewer reviewer-b --reviewer-command "python tools/reviewer.py"
```

执行器与 reviewer 在 Run 的 worktree 中运行，环境变量：

- `DISPATCH_TICKET_ID`、`DISPATCH_RUN_ID`、`DISPATCH_RUN_DIR`、`DISPATCH_EXECUTION_ROOT`、`DISPATCH_WORK_ORDER`、`DISPATCH_TICKET_PATH`、`DISPATCH_ATTEMPT`。
- reviewer 额外收到 `DISPATCH_REVIEWER`、`DISPATCH_VERIFY_JSON`、`DISPATCH_REVIEW_RESULT`；必须把 `{"verdict":"pass"|"fail","notes":"..."}` 写到 `DISPATCH_REVIEW_RESULT`。

边界：

- 执行器必须写 `receipt.json` 与证据到 `DISPATCH_RUN_DIR`；业务文件写到 `DISPATCH_EXECUTION_ROOT`。
- 执行器退出码不等于验收通过；`verify` 复跑票据命令并检查 diff/证据，verify 通过才算通过。
- 默认 `--until review`；degraded 退出码 2，仍需人工 `review --accept-degraded`。
- `--until land` 必须有独立 reviewer；reviewer 退出码 0 且 verdict=pass 才记录评审并 land；land 仍不 push、不合并目标分支。
- 每次尝试写 `auto/attempt-NN.log` 与 `auto.json`；reviewer 输出写 `auto/reviewer.log`；自动推进不跳过 review ledger 或 landing 记录。

## 落地到 integration branch（v0.5）

```bash
python <技能目录>/scripts/dispatch.py land 01
python <技能目录>/scripts/dispatch.py land 01 --into main --branch integration/demo --json
```

- 只接受已 `done` 且 review 通过的 worktree Run；主检出必须干净。
- 默认目标分支 `main`（否则 `master`/当前分支），默认 integration branch `dispatch/land/<run-id>`。
- 只创建本地 integration branch，**不 push、不切换、不合并目标分支**；写 `landing.json` 和 `.dispatch/ledger/landings.jsonl`。
- land 前复核 `verify.json` 的 `diff_hash`；review 后 worktree 再被修改会拒绝，必须重新 verify/review。
- 冲突时清理临时 worktree 与 integration branch，目标分支保持原样；成功后从 integration branch 人工开 PR。

## 子智能体与 Agent Team

**默认执行端就是子智能体与 Agent Team，不是看板。** 看板（`dsh push`）只作为可选的跨会话落库手段保留：它适合票面自足、写域独立、验收可命令化的票；需要边做边对齐的耦合任务走 team + handoff 或两阶段 brief 卡。

- 单票：`render <id> --agent <name>` 生成 `work-order.md`，交给一个子智能体。子智能体只写 execution root 和运行目录。
- 多票：`export --format agent-team` 生成 Team Lead 简报和每票工单。Team Lead 为每票起一个 teammate，先收 brief（目标、改动文件、计划、风险、问题），审核后再放行实现。
- 本技能只产出工单和团队简报，不创建任何外部卡片，也不依赖外部 HTTP 接口。
- 票面契约优先于人设和团队简报；写域、Acceptance、Verify 冲突时以票据为准。

## Codex 交接

```bash
python <技能目录>/scripts/dispatch.py export --format codex --tickets <票据目录> --output <工单文件>
```

把工单内容通过 stdin 交给 Codex：

```bash
codex exec --skip-git-repo-check --ephemeral -s read-only --color never -C <目标目录> -o <最后输出> -
```

不要把长 prompt 拼成 shell 参数，容易在 Windows 上被拆开；用 stdin。此技能只验证了“工单可被 Codex CLI 消费”，没有实现 Codex API 客户端。

## 安全边界

- 执行者不能直接改票据状态；只有 `verify` / `review` 能推进状态。
- `verify` 在 Run 的 execution root（默认是 `.dispatch/worktrees/<run-id>`）通过当前平台 shell 运行票据声明的命令，并额外检查主仓是否被污染；票据是受信任输入，但仍建议只给 L0/L1 自动执行。
- `verify` 的门禁防误不防恶意：执行者与验收者若共享同一文件系统，执行者理论上能改 `.dispatch/`；高信任要求时用独立用户/容器隔离。
- 写域检查基于 git diff 的规范化相对路径；symlink 越界是已知限制。
- L4 票据永远需要人工评审；不要用 `--human` 代替真实的人。
- `dispatch land` 只创建本地 integration branch，绝不 push、不合并目标分支，也不替代人工 PR 审查；land 前会复核 verify 的 worktree diff 哈希。
- `dispatch auto` 会执行你传入的任意 shell 命令；只在受信任的票据和受控环境中使用。它不绕过 verify/review，也不自动 push 或合并目标分支。
- 不要在票据里放真实凭据、私有绝对路径或生产密钥。

## 目录

- `SKILL.md`：本文件，技能入口。
- `src/agent_dispatch/`：自带框架；零运行时依赖。
- `scripts/dispatch.py`：从技能目录直接调用框架的包装器。
- `scripts/build_skill.py`：生成可复制的干净技能包（`dist/agent-dispatch-skill`）。
- `references/ticket-contract.md`：票据与回执契约细节。
- `references/codex-handoff.md`：Codex 工单交接方式。
- `templates/ticket.md`：最小票据模板。
- `agents/personas/dispatcher.md`：派单员人设；用于搜索、选择和写入 Persona。
