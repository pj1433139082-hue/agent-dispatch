---
name: agent-dispatch
description: 用票据契约、依赖分波、一票一 worktree、判据级证据、独立验收和异体评审，把任务派给 DSH 子智能体、Agent Team、Codex 或人工执行端。适用于多智能体任务编排、跨项目派单，以及把 ask-matt 产出的票据变成可执行工单。触发词：派单、任务编排、agent dispatch、票据、工单、依赖分波、写域、验收门禁、子智能体、Agent Team、Codex 工单。
---

# agent-dispatch · 票据派单台

本技能把“谁做、在哪个 worktree 做、能写哪、拿什么证据、谁来验收”变成可执行的文件契约。它自带一个零第三方依赖的 Python 框架（`src/agent_dispatch`），不要求目标项目安装 `dispatch`，也不依赖全局 PATH。当前版本 1.11.1。

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

## 你从哪来（接在现有流程上，前面的技能不用换）

如果你平时的流程是 `grill-with-docs → to-spec → to-tickets → implement`，**dispatch 替掉的是 to-tickets 之后的 implement 这一段**，前面的照旧。

| 你手上有什么 | 前半段照旧 | dispatch 接在哪 |
|---|---|---|
| 一句模糊需求 | `grill-with-docs` → `to-spec` | 出票后从「B 单票执行」开始 |
| 已有 spec | `to-spec` | `dispatch tickets <slug>`（要 S3 confirm）或手写票 → `dispatch lint` |
| 已有票（`tickets/` 或 `.scratch/<feature>/issues/`） | `to-tickets` | **直接走 B**：`brief → render → 执行端 → verify → review → land` |
| 什么都没有，只有一句话 | 可跳过前两步 | `align → select → sign → spec → confirm → tickets`（自带 S1–S5，可选入口） |

### 只打了 /agent-dispatch，该做什么

1. **先问一句：票在哪？**（`tickets/`、`.scratch/<feature>/issues/`、还是只有 spec）
2. 有票 → `dispatch lint` → `dispatch status` → 挑一张 frontier（`next: true`）→ 走 B
3. 没票但有 spec → `dispatch tickets <slug>`，或让对方先跑 `to-tickets`
4. 只有想法 → 建议先去 `grill-with-docs`，别在 dispatch 里想需求

### 没有 teammate 怎么办（四条路，选一条，别装）

| 你有的 | 怎么走 | 代价 |
|---|---|---|
| 会话里有 teammate（`list_agents` 看得到） | `render` → `handoff` → `send_message` | 真隔离，reviewer 能真换人 |
| 什么都没有，但能 `spawn_teammate` | **先建职能队友**（见 `docs/team/README.md` 八个角色），再派活 | 名字永久占用，一个会话最多 `maxMembers` 个 |
| 名额满了 / 要删旧成员 | `docs/team/roster-setup.md`：调 `maxMembers` 或装 `dsh-agent-team-roster` | 装插件要解 asar + 重启 |
| DSH 看板（票必须 L3+） | `dsh push --workspace <id>` → `dsh run` → `dsh outcome --mark-done --evidence` | 慢（十几分钟），要先有 workspace |
| 都没有 | `render` → 自己在 worktree 干 → `verify` → `review --reviewer <名字>` | **主代理自执行**；review 只是换名字，不是真异体——交付说明里必须写清 |

最后一条**不是错误用法**，是单 agent 环境的正常用法，只要如实标注。dispatch 的价值（写域、证据、验收、可回溯的 landing）在只有一个 agent 时同样成立。

> 判据：**能调 `list_agents` 才算有队友**。用 `globalThis.tools` 探测会得到 undefined（工具是词法注入的），别据此得出"没有团队"的结论。
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

## 配套技能（4 个，可与本技能并行使用）

| 技能 | 干什么 |
|---|---|
| `grill-dispatch` | 阶段 1：拷问 + 三视角取证 + 把对抗变成问题 |
| `to-spec-dispatch` | 阶段 2：出 spec + 三角色挑刺 + `confirm` |
| `to-tickets-dispatch` | 阶段 3：拆票 + `lint`/`plan` |
| `implement-dispatch` | 阶段 4：`brief → render → verify → review → land` |
| `implement-spec-dispatch` | 规格 → 票 → 落地，一条龙 |

## 测试计划

黑盒验收怎么做、覆盖矩阵、每轮协议：`docs/testing/test-plan.md`。

## 流程地图（四条）

| 流程 | 什么时候用 | 命令链 |
|---|---|---|
| **A 需求→票** | 模糊需求要变成可执行票 | `align → select → sign → spec → confirm → tickets → lint → stage` |
| **B 单票执行** | 已有票，要真的做完一件事 | `brief → render → handoff → start → verify → review → land`（可选 `closeout`） |
| **C 批量/自动** | 想半自动推进或整波落地 | `auto <id> --executor …` / `land --wave` |
| **D 运维恢复** | 状态不对、卡住、要体检 | `doctor [--fix] / sweep / repair / claim / release / gc / retry` |

完整版（谁产出谁消费、与其它技能的交界）：`docs/flows.md`。

## 主流程

0. **brief 是模板，不是一次生成就能批**（v1.1.0 起还查质量：每段 ≥8 字，五段不能完全相同；`无`/`none` 例外）：`dispatch brief <id>` 产出五段（理解/计划/要改的文件/风险/疑问），**必须把五段 `<填写：…>` 改成正文**再 `brief <id> --approve <人>`；占位内容会被拒。

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
6. **异体评审**：`review --reviewer <另一个名字> --verdict pass`；通过才进入 `done`。L4 必须加 `--human`；degraded 验收**放行**必须加 `--accept-degraded`（判 fail 是拒绝，不需要）。
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

**team 模式（v1.9.0）**：`select <slug> --mode team` 之后，三个角色各由一个 fresh teammate 产出（各自带角色卡与信息源隔离），回收后做一轮交叉评审写 `06-cross-review.md`；`sign` 会拒绝"还是模板"或缺 `Persona:` 行的证据。没有 teammate 工具时退回 `--mode solo`（主代理代做并标注）。见 ADR 0015。

## 发布前三条（v1.10.0）

- **评审窗口**：`review-window <slug> --open` 给选型包每份证据拍 sha256 快照；交叉评审后 `--close` 对比，有改动就 exit 1。team 模式下 `sign` 要求窗口已开且已关、且没有改动。
- **变异检查**：`mutate <id>` 把代码退回 run 的 `base_commit` 再跑票面 Verify——全都还过说明判据太弱（`mutation.json: status=weak`，exit 1）；至少一条失败才算 `killed`（exit 0）。`--per-file` 再逐文件回退，`weak_files` 列出"改了但判据没覆盖"的文件。
- **集成者**：`integrate --branch X --from a --from b [--verify-all "cmd"]` 把多条 land 分支按序合进一条新 integration 分支，合后可选跑全量回归；不 push、不碰目标分支，记录写 `.dispatch/ledger/integrations.jsonl`。

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

两条真机路径：**A** auto `--protocol full --until land` 全链路；**B** 老项目升级回归（无 `skill_version`/`deadline_seconds` 的旧 run 不许崩、不许迁移数据）。

**A 里现在还查 `dispatch wrap`**：跑完必须 `wrap_exit == 0`、`issues == []`，否则 acceptance FAIL——"没收口"直接变成红灯。退出码 0 = 都过。

## S3 规格门：空壳不能确认（v1.2.0）

- `confirm` 现在先检查七个必需小节：缺小节 / 为空 / 仍是占位（`（从问卷来`、`As a ... I want ...`、`每一行一条可验收项`…）都拒，`Delivery standard` 还必须至少有一条真实 checkbox。
- 逃生口：`confirm --force` 跳过空壳检查（迁移用，会在确认块留痕但不拦）。
- 确认块里写 `spec_sha256`：**确认后再改 spec，`tickets` 会要求重新 confirm**（改的是确认块之前的内容才算；在确认块后面追加不算改）。

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
   `dsh push --project <p>` 建卡 → 人在板上点 run（或 `dsh run <id>`）→ 结果用 `dsh outcome` 回写。看板地址以会话 runtime context 里的 **DSH Web GUI URL** 为准（端口每次可能不同），请求要带 `sec-fetch-site: same-origin`。
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
5. **done ≠ landed**：`review` 通过只是票 done，代码还在 worktree 分支；要进 integration branch 得 `land`。`status` 会标 `-> 未落地（dispatch land <id>）`，`wrap` 会报未落地 run 数。
6. **票面的 `**Status:**` 只是作者标记**：真实状态看 `dispatch status` / `.dispatch/state.json`，工具不会回写票面。

### 身份：名字不等于执行者（有硬门，分三层）

`--agent` 只是写进工作单的声明；`--reviewer` 有**三层硬门**（ADR-0008 D5 + v0.50）：

| 层 | 规则 | 触发条件 |
|---|---|---|
| 1. 名字 | `reviewer` 等于票的 `Owner` 或 run 的 `claimed_by` → **拒绝** | 所有等级 |
| 2. 自审 | L0/L1 可 `--self-reviewed` 显式留痕放行；**L2+ 一律不许** | reviewer 与执行者同名时 |
| 3. 读包证明 | **L2+ 必须 `--packet-hash <review-packet.md 的 sha256>`**，哈希不符即拒；通过后 `packet_attested=true` | L2/L3/L4 |

- L4 还要 `--human`（人工评审）。**顺序是：先有 packet → 再对 `--packet-hash` → 最后才问 `--human`**；不跑 `review-packet` 就永远看不到 human 的报错。
- `--human` 现在会记进 `review.json` 与 ledger 的 `human: true`（v0.71 起；以前只在退出码里，事后无法区分）。
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

## 依赖与分波的真实语义（实测 v0.63）

- **`plan` 的 frontier 是静态拓扑**：它不看 state，done 的票照样列在 frontier 里。要"现在能开工的票"用 **`status`**，别用 `plan`。
- **写域冲突只比同波**：同波两票写同一路径 → `Conflict A / B: path`；被依赖链拉开到不同波的票即使写域重叠，**一个字都不报**。
- **`status` 的 blocked 只列直接阻挡**：`21 blocked by 20` 不会告诉你 20 又被 19 挡着，要自己顺链。
- **未跟踪的票文件**：`verify` 会把 `tickets/…` 列进 "outside the write scope" 但判 ok（流水线文档豁免）；`land` 不豁免，落地前必须提交。

## 人设与导出的实测细节（v0.64）

- `personas list` 会把**同一份人设列两次**：`assign` 把它复制到 `tickets/personas/`，下次搜索就命中内置+本地两份（内容相同）。只想看内置的加 `--search-root <技能目录>/agents/personas`。
- `assign` 写的是**路径**（`personas/dispatcher.md`）不是名字，同时复制文件 + 追加 `.dispatch/assignments.jsonl`（含改票前后的 `ticket_hash`）。
- `context` 只读**仓库根**的 `AGENTS.md` / `CLAUDE.md` / `CONTEXT.md`；三者都没有就写一句 "(no … at the repository root)"，不会去子目录找。
- `export`：`agent-team` 有 Team Lead 简报 + 每票段；`codex` / `generic` 是平铺的票段（generic 多个总标题）；`dsh-team` 是 JSON 数组。人设都会展开成 `### Agent persona`（不是只给路径）。

## repair 与 gc 的实测细节（v0.70）

**repair**
- 证据优先级 **review > closeout > verify**：想造 evidence_mismatch 得改 `review.json`，改 `verify.json` 没用。
- evidence_mismatch：exit **0**，但**这张票不写**（其余照写）；打印 `EVIDENCE-MISMATCH`。
- run_id 冲突：exit **1**，stderr 打 `CONFLICT`；此时若仍写了别的票，输出是 `Written: partial (conflicts skipped)`（v0.70 起；以前一律 `Written: yes`，容易误读成冲突被处理了）。
- 只重写"有 run 且不冲突"的票的 `updated_at`；**不清理幽灵索引项**（那是 `doctor --fix`）；state.json 全丢时只重建"有 run 的票"。

**gc**
- `REMOVE` 删：worktree 目录 + `dispatch/<run_id>` 分支 + 释放租约；**不删** run 目录、`landing.json`、`dispatch/land/<run_id>` 分支、state 条目、票面。
- `landed` 判定 = `run 目录里有 landing.json`，与是否合并进 main 无关。
- `HOLD` **不释放租约**；文本模式**不显示 worktree 路径/分支名**（要 `--json`）。
- **没有单票过滤**；孤儿 run、worktree 已手工删掉的 run 都静默跳过（无行、无汇总）。
- 永远 exit 0。

## 运维命令的边界（实测，v0.61）

| 命令 | 必须知道的三件事 |
|---|---|
| `claim` / `release` | 都要**先有 run**（brief+render）；`claim` 对 done/failed 票没有状态门；`release` 释放该 run **全部**租约，没有 run 时是 no-op（exit 0）；同 run 再 `claim` 会**续期**；退出码 0/3(冲突)/4(写域展不开) |
| `sweep` | 只读、永远 exit 0；**文本模式只印一部分字段**（last_artifact / deadline_seconds 要用 `--json`） |
| `repair` | 默认 dry-run；`--write` 会把整张 state 的 `updated_at` 换成 `run.created_at`；run_id 冲突 → exit 1，evidence_mismatch 只打印不拦 |
| `gc` | `--apply` 会**删掉 worktree 分支**；只处理索引里还有的 run（孤儿 run 不提示）；永远 exit 0 |
| `seat` | 超 cap 不报错，只给负数 `free`；`inactive` 只在满员时才进建议 |
| `doctor --fix` | 同样会重写 `updated_at`；只做安全修复，不动票、不删 run |

## stage 的两个细节（v0.71）

- `stage <slug> --prompt` 的退出码是 **0 = 有问题要问 / 2 = 没有问题（已完成）**；不带 `--prompt` 的 `stage` 未就绪才是 exit 1。
- 输出的 `stage` 字段到顶时是 **`done`**（不是 `s5`）；且 **s4/s5 是仓库级判断**（看 `tickets/*.md`），不是按 slug 的——任何 slug 只要有票在 `tickets/` 就会显示 s4/s5 OK。

## pre-commit 钩子（v0.87）

```bash
dispatch install-hooks          # 写 .git/hooks/pre-commit
dispatch install-hooks --force  # 覆盖已有的
```

- 钩子内容只有一层：`[ -d .dispatch ] || exit 0` → `python <skill>/scripts/dispatch.py wrap --root .`，非 0 就挡提交。
- 仓库里没有 `.dispatch/` 时钩子直接放行（不会拦住无关仓库）。
- 绕法：`git commit --no-verify`。

## 团队名册：名额与删除（v1.0.0）

- **名额**：官方 profile 写死 `maxMembers: 8`；建人时报 `Team member limit 8 reached` 就是这个。要更多就在**真正启用了 Agent Teams 的那个 profile**（本机是 `desktop`；`web` 没装，写进去静默无效）的 `cordis.patch.yml` 覆盖 `agent-team` 行（实测**不用重启**）。
- **删除**：官方 roster 只增不减（`TeamRoster` 无 remove）。要删装 `dsh-agent-team-roster`（`delete_teammate` / `rename_teammate` / `cleanup_team`）。
- ⚠️ `cleanup_team { scope: "teammates" }` 的判据是"当前没有回合在跑"——**空闲的职能队友也在射程内**（`scope:"all"` 还会删已完成任务）；要留队就逐个 `delete_teammate`。
- **重启范围**：改 `maxMembers` 不用重启；**新增插件行（insert）需要重启**。`patchReload` 这个键在 0.2.1-rc.3 不存在。
- `delete_teammate` 会**中断正在跑的回合**并丢弃未投递消息。
- 完整步骤（Windows 下解 asar、junction 必须叫 `node_modules`、新增 insert 行后要**完全退出进程**再打开）：`docs/team/roster-setup.md`。

## 团队

八个职能队友（scout/planner/executor/verifier/reviewer/auditor/fixer/scribe）、派活模板与三条硬规矩：`docs/team/README.md`（ADR-0013）。

## 这个月发生了什么

0.1 → 1.7.2 的主线、四条流程实战结论、三次"看起来绿其实是假的"：`docs/CHANGELOG-2026-10.md`。

## 术语

用错就会出事的词（判据 vs 验收项、执行根、快照判据、重复失败指纹、落地区间、收口）：`GLOSSARY.md`。

## 跑全量测试（v0.86）

```bash
python scripts/test_parallel.py -j 6   # 94 个文件约 150s（按测试函数数均衡）
```

## 两个实测补丁（v0.72）

- `sign` 现在支持 `--note "<一句话>"`，写进 `99-summary.md` 的 `- 备注：` 行（老会话里出现过 `unrecognized arguments: --note`）。
- `verify` 的「主仓脏」判定现在忽略 `.scratch/`（本地 issue tracker 的常用目录，老会话因为它整票 verify 失败）。

## 多会话并行：render --claim（v0.82）

- `render <id> --claim`：开局的同时把写域换成**文件租约**（`.dispatch/locks/`）。
- 第二个 run 想动同一批文件 → exit 3，stderr 打 `LEASE conflict <path> held by <票>`。
- 收工别忘了 `release <id>`（`land` 会自动释放）；`gc` 的 REMOVE 也会释放。
- 不用 `--claim` 就还是老行为：两个会话靠 `plan` 的冲突提示 + 人自觉。

## 票在 render 后被改：现在能提前看见（v0.81）

- `status`：该票那行会标 `-> 票在 render 后被改过（revert 或 retry 01）`
- `doctor`：报 `tickets edited after render: 01 (revert or dispatch retry)`，`wrap` 也会带出来
- 处置：把票改回去（`git checkout -- tickets/01.md`）或 `retry` 重新开局；不要指望 verify 能过

## 写票时顺手绑人格（v0.94）

```bash
dispatch new 01 --title "recon runtime" --what "写报告" --write-scope reports/01.md --persona dispatcher.md
# Created tickets/01-recon-runtime.md
# Assigned 01 -> personas/dispatcher.md (派单员)
```

`--persona` 接受 `tickets/personas/` 下的文件名（或 `--search-root` 找得到的名字），会复制人格文件、写 `- Persona:` 行、追加 `assignments.jsonl`。

## 子根只能看不能跑（v0.96）

- 把状态仓放 `.planning/<任务>/dispatch/`（在别的 git 仓库里面）时：`status`/`roots`/`status --all` 都能看，但 `render` 会 **exit 7**：
  `RENDER root is inside another git repository (toplevel=…); run dispatch from that repository or git init this directory first`
- 要在子根里真干活：给子目录 **单独 `git init`**，或者把状态仓放回仓库根。
- `status --all` 现在**包含当前根**（v0.96），不用再 `status` + `status --all` 跑两遍。
- `roots` 跳过 `.dispatch/` 内部（不再把 `.dispatch/tmp/*` 的探针根报成根）。

## 人格门：L2+ 必须有 Persona（v0.93）

- `render` / `auto` 在 Risk ∈ {L2,L3,L4} 且票面没有 `Persona:` 时**拒绝开局**，exit **6**：
  `ticket 01: risk L2 needs a persona; run dispatch assign 01 --persona <name>`
- 阈值可配：`.dispatch/config.json` 的 `persona_policy` = `l2`（默认）/ `l3` / `l4` / `off`。
- 为什么放在 render 而不是 new：`new` 只写票，`render` 才真正占 worktree/租约——门要在花资源之前。
- **顺序**：人格门在 **brief 门之前**（v0.96 起）；否则 `require_brief=true` 时先看到 exit 1 的 brief 报错，会以为人格门没生效。
- **阈值对 render 和 auto 一致**（v0.96 修）：`persona_policy` 三个值 `l2/l3/l4` 两条路径都按同一张表判定。
- 为什么不是 L0/L1：小改强绑人格只会增加摩擦；L2+ 才是"要异体评审"的级别。

### 人格绑定与审计（v1.8.3）

- **run 记事实**：`render` 把角色卡的 `sha256`、来源、名字写进 `run.json.persona`；票面 `Persona:` 仍是意图，可换。
- **豁免留痕**：`persona_policy=off` 或 `render/auto --allow-unassigned-persona` 会在 run 里记 `persona_waiver: {source, at}`——门可以关，但关了有记录。
- **verify 只降级**：角色卡在 render 后被改、L2+ 新 run 回执没自报 `persona`、回执与绑定不一致 → `status=degraded`（exit 2），review 显式 `--accept-degraded` 才放行；不直接 failed。
- **老 run 不追溯**：v1.8.2 及以前的 run 没有绑定字段，按 legacy 处理，不判降级。
- **看得见**：`status` 行尾显示 `persona <名字>` 或 `persona waived (<来源>)`；`wrap` 只对"该绑没绑也没豁免"的未落地 run 报 issue。

## 根级汇总：status --all（v0.93）

- `dispatch status --all`：把仓库里所有 dispatch 根（含 `.planning/*/dispatch`）的票与 frontier 一起打出来。
- 默认不聚合（多根输出长）；`wrap` 只在"本地没票"时提示 `other dispatch root(s) found`。

## 状态仓可以在子目录，但根上会看不见（v0.92）

- 有人图干净，把状态放到 `.planning/<任务>/dispatch/`，用 `--root` 指过去跑。**这没问题**，但仓库根上 `dispatch status` 会显示 `Frontier: -`、`wrap` 会报 `tickets directory is missing`。
- `dispatch roots` 会把这些根找出来（最长 4 层）：`roots → <path> (6 ticket(s))`。
- `wrap` 在发现"没有本地票"时也会提示 `other dispatch root(s) found: …`。
- 建议：**要么用默认根**（`tickets/` + `.dispatch/` 在仓库根），**要么**在根上放一个 README 指路。

## 票面可选字段 Requires:（v0.91）

`- Requires: local | network | ssh | browser`（默认 `local`）。当前只做解析 + lint 警告（`environment_needed` / `invalid_requires`），**不做硬门**——执行端能力清单还没定。

命令表以 **`docs/commands.md`（随包分发的自动生成版）** 为准；在仓库里跑 `python scripts/gen_command_table.py` 重写，测试 `--check` 比对，漂移即红。（`scripts/build_skill.py`（打包到 `dist/`）与 `scripts/install_skill.py`（镜像到 `~/.agents/skills`，会删掉陈旧文件与 `__pycache__`）都是仓库脚本，不随包分发。）

## Verify 必须"本机一次跑通"（v0.89，来自 ts-sweep-server 的教训）

写票时的**写作提示**（不是运行期检查——`verify` 只强制"别超时"，其余三条靠人）：

1. **本机可跑**：不依赖 ssh / 远端机器 / 浏览器 / 需要登录的服务。
2. **幂等**：连跑两次结果一样，不会因为"第一次改了状态"而第二次失败。
3. **无网络**：不要在 Verify 里下载、打 API。
4. **快**：单条 < 5 分钟；跑不完就拆成多条判据或落快照。

需要远端事实时：**先跑一次把结果落成文件（带时间戳/主机名），Verify 只断言这个快照**。

**判据强度的唯一可执行定义：变异检查**——把实现故意改坏（改错返回值、删掉关键分支），Verify **必须变红**。改坏了还绿，说明这条判据只验证了"命令能跑"，没验证"东西对"。`echo ok` / `print(1)` 这类恒真命令会被 lint 标 `weak_verify`。

失败重复也会被点名：同一张票连续 3 次报同样的错误，`verify` 会打印
`VERIFY repeated failure: … Re-running will not change it — fix the environment the command needs, or rewrite the criterion.`

## 波次落地：`land --append` 累积到同一条分支（v1.4.0）

```bash
dispatch land 01 --branch wave/all
dispatch land 02 --branch wave/all --append   # 合进同一条分支，而不是新建
dispatch land --wave --branch wave/all --append   # 整波一条分支
```

- 默认行为不变：每张票一条 `dispatch/land/<run-id>`，互不包含（安全，但需要人工合并）。
- `--append` 把 run commit **merge 进已存在的 integration 分支**；不加它而分支已存在 → 报错并提示两条路。
- 仍需人工 push / 开 PR；land 始终不碰目标分支。
- **`--verify`（v1.5.0）**：落地后在 integration 分支上复跑票面 Verify，打印 `VERIFY-AFTER <id>: pass|fail`；失败退出码 1，逐条列出失败命令，并把 `landing.json` 的 `status` 记成 **`landed-unverified`**（分支已建，但没通过合后验证）。用途：抓"worktree 里能过、合进分支就挂"的票（典型：判据依赖被 gitignore 的产物）。
- **整波一次验（v1.6.0）**：`land --wave --branch X --append --verify` 会在合完之后，把**所有落地票的 Verify 去重后在同一条分支上跑一次**，打印 `VERIFY-AFTER wave X: pass|fail (N unique command(s))`；失败退出码 1。不带 `--branch` 时仍逐票各验一次。
- **整分支全量回归（v1.8.0）**：`land <id> --verify-all "<命令>"`（可重复，重复命令只跑一次）落地后把**你给的回归命令**放进 integration 分支的临时 worktree 执行，打印 `VERIFY-ALL <id>: pass|fail on <分支>`；失败退出码 1、逐条列出失败命令，并把 `landing.json` 的 `status` 记成 **`landed-unverified`**、`verify_all_status` 记 `fail`（记录里另有 `verify_all.commands` 明细）。与 `--verify` 的分工：`--verify` 复跑票面 Verify（证明这张票），`--verify-all` 跑整套回归（证明这条分支）。整波用法 `land --wave --branch X --append --verify-all "python -m pytest -q"` 只在整波落完后跑一次，打印 `VERIFY-ALL wave X: pass|fail (N command(s))`；**不带 `--branch` 会在落地前直接报错**（逐票分支各跑一遍全量回归不是本意）。`--verify-all-timeout` 默认 1800 秒/条（票面 `--verify` 仍是 300 秒）。

## retry 会重写 context.md（v1.3.0）

- 若 `render --with-context` 生成过 `context.md`，`retry` 会把它重写成 `attempt N of the same run`，执行端能看到"这不是第一次"。
- `review-packet` 的 `ticket` / `receipt` / `verify` / `closeout` 哈希全部按**原始字节**算，可直接用 `sha256sum` 核对。

## done ≠ landed（v0.79）

- `review` 通过 = 票 **done**，代码还在 worktree 分支；要进 integration branch 必须 `land`。
- `status` 会给未落地的 done 票标 `-> 未落地（dispatch land <id>）`。
- 批量落地前先预览：`dispatch land --wave --dry-run`（只打印 WOULD / SKIP，不建分支）。
- `wrap` 会把"未落地的 run"算进 issues，Next 里给 `land --wave --dry-run`。

## 会话收口三步（v0.73，来自两次真实会话的教训）

1. `dispatch status`：末行会打 `Session wrap-up: N failed (...); M active run(s) (...)` —— 有这行就说明这个会话没收干净。
2. `dispatch doctor`：还会报 `uncommitted files will block land: ...`（`.dispatch/`、`.scratch/` 不算）。
3. 逐项处理：failed → `retry <id>`；卡住的 run → `release <id>` / `sweep`；已完结的 → `gc --apply`。

**一次会话推几张票**：实战里 10 张票把上下文推到 5.4M tokens 直接 `prompt_too_long`。经验值：**一次会话 3–5 张**，或上下文过 150k 就换会话——票是自包含的，换会话不丢信息。

## 命令速查

| 命令 | 用途 |
|---|---|
| `setup [--tickets 目录] [--executor-mode teammate\|dsh\|command] [--default-reviewer 名字]` | 写 `.dispatch/config.json` + `.gitignore(.dispatch/)`；`default_reviewer` 只在 `review` 没传 `--reviewer` 时生效；幂等 |
| `handoff <id> [--to <agent>] [--json]` | 打印"该发给谁、发什么"的交接内容（工作单路径、执行根、分支、回执位置） |
| `install-hooks [--force]` | 装 pre-commit 钩子：有 `.dispatch/` 就跑 `wrap`，不干净挡提交（`--no-verify` 可绕） |
| `roots [--json]` | 扫仓库里**其它 dispatch 根**（`dispatch/config.json`、`.dispatch/state.json`、`dispatch/tickets`）——子目录里跑过的活，根上默认看不见 |
| `wrap [--json] [--fix]` | **会话收口一条命令**：状态计数 + doctor 全部问题 + **未 landing 的 run 数** + 下一步该跑什么；干净 exit 0，有事 exit 1 |
| `doctor [--json] [--fix]` | 只读体检：票能否 lint、索引与磁盘是否一致、失败票、超期 run、活跃租约；`--fix` 只做安全修复（重建索引 + 删过期租约）；有问题 exit 1 |
| `release <id> [--json]` | 释放该票的文件租约（卡住的 run 用它放锁；幂等，没租约也成功） |
| `retry <id> --reason "为什么再试一次"`（**必填**） | 把 `failed` 的票拉回 `running` 再验一次；旧的 verify/review/closeout 归档到 `attempts/`，索引里留 history |
| `confirm <slug> --by <人> --via <dialog 或 card> [--note …]` | 把 S3「规格已核对」写进 `docs/specs/<slug>.md` 的 `## Confirmation`；`tickets` 未确认前拒绝拆票（`--force` 跳过） |
| `sign <slug> --by <人> --via <dialog 或 card> [--hold 或 --reject] [--note "..."]` | 把甲方签字写回 `99-summary.md`（签字人 + 勾选 + 确认方式）；**`--via` 必填**，不写来源不许签 |
| `stage <slug> [--json] [--prompt]` | S1–S5 一屏状态；`--prompt` 输出该阶段要人回答的问题（喂弹窗/决策卡）：问卷 / 选型 / 签字 / 规格 / 票；`next` 指下一步，未就绪 exit 1 |
| `claim <id> [--ttl-minutes 15]` | 把票的写域展开成**文件租约**（`.dispatch/locks/`）：被别的活租约占着就 exit 3，不让两个 run 同时写同一文件 |
| `gc [--apply]` | 回收 ended run 的 worktree：干净且已 land → REMOVE；有未提交改动或未 land → HOLD |
| `seat [--cap 8] [--occupied N] [--agent <名字>] [--inactive a,b]` | 派单前查名额：占用/上限/可回收 inactive，给出可/需回收/阻塞 |
| `review-packet <id>` | 冻结票据、diff、回执与验收证据成评审包；`hashes.diff` 与 `verify.diff_hash` **同源同值** |
| `dsh <push/status/outcome/update/archive/run/delete>` | 投递与看板联动（可选路径，不是默认执行端） |
| `lint` | 校验票据；有错非零退出 |
| `plan [--json] [--done <id> ...]` | 拓扑波次、frontier、写域冲突 |
| `status [--json]` | 每张票的有效状态 |
| `new <id> ...` | 生成一张可 lint 的票据 |
| `render <id> --agent <name> [--no-worktree] [--claim] [--seat-cap N] [--with-context] [--require-brief] [--deadline-minutes 15]` | 创建 Run、worktree 和 work-order（记 `skill_version` 与 `deadline_seconds`），状态进入 claimed |
| `start <id>` | claimed → running |
| `verify <id> [--allow-main-drift] [--timeout 300]` | 独立验收；passed/degraded → review，failed → failed；退出码 0/2/1 |
| `review <id> --reviewer ... --verdict <pass 或 fail> [--accept-degraded] [--self-reviewed] [--human] [--notes "..."] [--packet-hash <sha>]` | 异体评审；通过 → done，并追加 review ledger。**L2+ 必须给 `--packet-hash`**（L0/L1 可选，给了也会记 attested） |
| `land <id> \| --wave [--into 目标分支] [--branch 前缀] [--require-closeout] [--require-attestation] [--no-require-packet] [--verify] [--verify-all "命令"] [--verify-all-timeout 1800] [--append] [--continue-on-error] [--dry-run]` | 把已验证 Run 合入本地 integration branch；**默认要求 review-packet.md 存在**；目标分支不变，不 push |
| `auto <id> --executor <shell> [--agent <name>] [--resume] [--max-attempts N] [--timeout 1800] [--verify-timeout 300] [--until review 或 land] [--reviewer ... --reviewer-command ...]` | 半自动推进：render → 执行器 → verify（可重试）；`--until land` 需独立 reviewer 命令 |
| `auto <id> --executor <shell> --protocol full [--env-hint "<命令>"] [--require-brief]` | 带协议跑：注入 context + 环境前置、检查 brief 门、每次 verify 后发 checkpoint、跑 closeout；`--until land` 必须 closeout pass 才 land |
| `answer <slug> --answers <json>` | 无人值守：按顺序把 JSON 答案填进问卷空 `> ` 行；条数不符即拒 |
| `review-window <slug> --open\|--close` | 选型包证据快照：交叉评审前开、评审后关；有改动 exit 1；team 模式签字前必须有干净窗口 |
| `mutate <id> [--timeout 300] [--per-file]` | 变异检查：base_commit 重跑 Verify（全过=weak）；`--per-file` 逐个回退改动文件，找出"改了但判据没覆盖"的文件 |
| `integrate --branch X --from a --from b [--verify-all "cmd"]` | 多分支集成：按序 merge 进新分支，合后可跑全量回归；不 push |
| `assign <id> --persona <文件或短名> [--by <名字>]` | 把可解析的人设写入票据 Persona；源文件复制到 `tickets/personas/`，并记 `.dispatch/assignments.jsonl` |
| `personas list [--search-root <目录>] [--json]` | 搜索可解析的 agent 人设（本地角色卡、agency、GSD、ruflo 等） |
| `personas show <文件或短名> [--json]` | 读取单个 persona 的身份、能力与提示词 |
| `export --format <agent-team / dsh-team / codex / generic>` | 只读导出；`agent-team` 生成 Team Lead 简报 + 每票工单 |
| `context <id> [--json]` | 生成 `.dispatch/context/<id>.md`：入口文档摘录 / 同票历史运行 / 阻塞邻居 / 踩坑索引 |
| `brief <id> [--check 或 --approve <人>]` | 两阶段：只读 brief 模板、校验五段非空、记录审批（票据与 brief 双哈希） |
| `checkpoint <id> [--label <名>] [--list]` | 发布不可变检查点（manifest + diff.patch + status + restore.md），`--list` 看代际 |
| `questions <slug> [--json]` | 把 `03-adversary.md` 的假设转成可直接问甲方的问题（配合 `ask_user_question`） |
| `select <slug> [--with 角色1,角色2] [--add ID[:PERSONA]] [--list]` | S2：出选型证据包 `docs/selection/<slug>/`——三角色必选（开源借鉴 / 搜索取证 / 对抗审查），可选领域约束与成本守护，其余角色可自带 persona 追加 |
| `sweep [--json]` | 只读巡检：每条 active run 的 `age_seconds / last_artifact / idle_seconds / has_receipt / deadline_seconds / over_deadline`；**不自动 kill** |
| `repair [--write] [--json]` | 从 `.dispatch/runs/*/run.json` 反向重建 `state.json`；默认 dry-run；冲突票**不写**并 exit 1 |
| `align <slug> [--level quick 或 standard 或 thorough]` | S1：出需求问卷 `docs/questions/<slug>.md`，第一段就是档位选择（3 / 6 / 10 问） |
| `closeout <id> [--json]` | 对照 票面 / brief / diff 出收口报告；`land --require-closeout` 才强制 |
| `spec <slug> [--force]` | S3：问卷答满 **且 S2 已签字** 才允许写规格骨架（--force 跳过签字门） `docs/specs/<slug>.md`（Problem / Solution / Stories / Delivery standard / Decisions / Testing / Out of scope） |
| `tickets <slug>` | S4：按规格的 `## Delivery standard` 逐条生成草稿票到 `.dispatch/drafts/<slug>/`，补 Write scope 与 Verify 后进 `tickets/` |

**`--tickets` / `--root` 不是通用的**（v0.97 实测，40 个命令逐个 `--help` 核对）：

- 吃 `--tickets` 的 17 个：`lint` `plan` `render` `context` `brief` `closeout` `review-packet` `claim` `wrap` `setup` `handoff` `doctor` `auto` `status` `export` `assign` `new`
- 吃 `--root` 的 35 个：除下列 5 个之外全部支持——`lint` `plan` `dsh` `personas` `new`
- **不吃 `--tickets` 的**：`verify` `review` `land` `start` `release` `retry` `checkpoint` `seat` `sweep` `gc` 等（传了会 `unrecognized arguments`，exit 2）
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

`--until land` 还会先生成 `review-packet.md` 并把 `DISPATCH_REVIEW_PACKET` 交给 reviewer；reviewer 回执里的 `packet_hash` 与实际包**不一致** → `review-invalid`，不 land。**L2+ 的票在 auto 里也必须回填哈希**（不回填同样 `review-invalid`），L0/L1 不强制。

## auto 的 preflight 是全局的（实测 v0.66）

- 它会因为**别的票**遗留的超期 run 直接 exit 1（报 `runs past their deadline: 23`），哪怕你这次要跑的票干干净净。
- `doctor --fix` 不会结束 claim 住的超期 run；要么先把那张票 `retry`/`release` 处理掉，要么这次 `--force`。
- `auto/feedback-N.md` 只写"哪条判据挂了"，**不含 diff、不含执行器 stdout**；执行器要自己打开它读原因。
- `auto.json` 的 `protocol` 里没有 "full" 字面值，只有 `enabled: true` + `context/env_hint/brief_gate/last_checkpoint/closeout`。

## --protocol full 到底注入什么（实测 v0.62）

- **只写两个文件，不加环境变量**：`<run>/context.md`（票面 + 写域 + 完成定义 + Verify + 项目入口文档前 60 行 + 同票历史 run + 阻塞邻居 + 坑笔记清单）和 `work-order.md` 末尾的同一份内容。执行器**不读 `DISPATCH_WORK_ORDER` 就等于白写**。
- `--env-hint` 追加到 work-order 的 `## Environment prerequisites`，并记进 `run.json.env_hint`。
- checkpoint 在**每次 verify 之后、closeout 之前**写：`checkpoints/NNN-attempt-N/{checkpoint.json,status.txt,diff.patch,restore.md}`，代际**按 run 隔离**，`current.json` 原子指向最新。
- `--accept-degraded` 只对 `--until land` 分支有用；`--until review` 不读它。

## checkpoint 的 diff.patch（v0.66 起）

- 未跟踪的新文件（`??`）以前**不会进 diff.patch**（`git diff` 看不见未跟踪文件，patch 是 0 字节）；现在会以 `--- /dev/null\n+++ b/<path>` 的形式补进去。
- `restore.md` 的恢复步骤是 `git checkout <base> -- .` + `git apply <generation>/diff.patch`；二进制文件仍只有 sha256，没法从 patch 还原。

## closeout 的五条判据（实测）

1. `verify.json` 存在且是 passed/degraded
2. **receipt.criteria 条数 == 票面 Acceptance 条数**（老式 `evidence` 数组会被算成 0 → 必 fail）
3. 改动都在写域内
4. 改动都在 brief 声明内（**仅当 brief 至少声明了一个"像路径"的 bullet**）
5. brief 声明的每个路径都真的改了

"像路径"判得很粗：`- `/`* ` 开头、取第一个空格/冒号/括号前的 token，含 `/`、`\`、`.txt`/`.py`/`.md` 就算。brief 正文里随手写的文件名也会被当声明。

## auto 与 retry 的实测口径（v0.69）

- **退出码**：`auto --until review` 0 = passed、2 = degraded、1 = failed；`landed` 只在 `--until land` 时出现。
- **执行器必须先提交进 git**：`auto` 用 `base_commit` 建 worktree，未提交的 `tools/xxx.py` 在 worktree 里不存在。
- **两个目录别混**：`auto/` 是 auto 写的（`attempt-NN.log`、`feedback-N.md`，**不补零**）；`attempts/` 是 `retry` 建的归档（`verify-01.json` 等）。
- **retry 后不能直接再 auto**：票变 running，`auto` 会拒（`already has an active run`）。救法：自己重跑执行器 + `verify`，或 `review`/`land` 接着走。
- **`--force` 只跳过 preflight**，不跳过"已有 active run"这类前置检查。
- **失败的 auto 不会刷新 auto.json**：票后来 done 了，`auto.json.status` 仍是 failed——真实状态看 `status`/`state.json`。

## degraded 的判定与记录（v0.69）

- **触发**：某条判据的**全部**证据都是 attested（只有 `kind:"note"` 算 attested；file/inline/absent/command 都不算）→ `verify` 判 degraded，**退出码 2**，票进 `review`（不是 failed）。判定按**整条 criterion** 算，与证据书写顺序无关（v1.8.2 修）。
- **拒绝可重试**：不带 `--accept-degraded` 的 `review` exit 1，只有一句 stderr，**不写 review.json / 不写 ledger / 状态不变**。
- **接受后**：`review.json` 的 `status` 是 **passed**（不是 degraded），降解事实在 `verify_status: degraded` + `accepted_degraded: true`。

## auto --resume（v0.83）

- `retry <id>` 之后票是 `running`，直接 `auto` 会被拒（`already has an active run`）。
- 加 **`--resume`** 就继续那个 run（不新建 run、不改 run-id），跑执行器 → verify。
- 也可以用 `--force` 跳 preflight，但 `--force` 不等于 `--resume`：前者只管 preflight。

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
- 写域检查基于 git diff 的规范化相对路径；改动路径穿过 symlink/junction 会被**判死**（v0.30，`link_in_path`）。
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
