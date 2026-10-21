---
name: agent-dispatch
description: 用票据契约、依赖分波、独立验收和异体评审，把任务派给 DSH 看板、Agent Team、Codex 或人工执行端。适用于多智能体任务编排、跨项目派单，以及把 ask-matt 产出的票据变成可执行工单。触发词：派单、任务编排、agent dispatch、票据、工单、依赖分波、写域、验收门禁、DSH 看板、Agent Team、Codex 工单。
---

# agent-dispatch · 票据派单台

本技能把“谁做、能写哪、拿什么证据、谁来验收”变成可执行的文件契约。它自带一个零第三方依赖的 Python 框架（`src/agent_dispatch`），不要求目标项目安装 `dispatch`，也不依赖全局 PATH。

## 何时使用

- 一个任务要拆成多张有依赖关系的票据，分给多个 agent 或人。
- 需要限制每个执行者的写作用域，防止越界改动。
- 需要独立复跑验证命令、检查真实 git diff、记录证据哈希。
- 需要异体评审，避免实现者自己宣布完成。
- 需要把 ready 票据投递到 DSH 任务看板，或导出成 Codex 工单。

## 何时不用

- 单文件、一步就能完成的小改动：直接用目标项目的测试/评审流程即可。
- 只需要讨论方案、还没有可执行任务：先用 `grill-with-docs` 或 `to-tickets`。
- 需要替代 DSH Agent Teams、Codex 或 CI：本技能只做票据、工单、门禁与投递，不做执行器。

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

## 主流程

1. **建票**：一张票一个 Markdown 文件，写清 `What to build`、`Blocked by`、`Write scope`、`Verify`、`Acceptance`。
2. **校验与分波**：`lint` 拒绝缺字段、自依赖、环、未知依赖；`plan` 输出拓扑波次、frontier 和同波写域冲突。
3. **派发**：
   - 本地执行：`render <id> --agent <name>` 生成 `work-order.md`，票据进入 `claimed`。
   - DSH 看板：`dsh push` 创建卡；`--mode team` 创建一张 `teamRun` 父卡和每票一张子卡。
   - Codex：`export --format codex` 生成工单，交给 Codex 会话。
4. **执行者只写两处**：业务文件 + 运行目录里的 `receipt.json` 和证据文件；**不能改票据状态**。
5. **独立验收**：`start` → `verify`。`verify` 复跑票据命令、检查 git diff 是否越出写域、核对证据哈希；失败进入 `failed`。
6. **异体评审**：`review --reviewer <另一个名字> --verdict pass`；通过才进入 `done`。L4 必须加 `--human`。
7. **回写外部执行**：DSH 卡执行完后可用 `dsh outcome` 写外部结果；它**不替代** `verify`。

## 命令速查

| 命令 | 用途 |
|---|---|
| `lint` | 校验票据；有错非零退出 |
| `plan` | 拓扑波次、frontier、写域冲突 |
| `status [--json]` | 每张票的有效状态 |
| `new <id> ...` | 生成一张可 lint 的票据 |
| `render <id> --agent <name>` | 创建 Run 和 work-order，状态进入 claimed |
| `start <id>` | claimed → running |
| `verify <id>` | 独立验收；通过 → review，失败 → failed |
| `review <id> --reviewer ... --verdict <pass 或 fail>` | 异体评审；通过 → done |
| `export --format <dsh-team / dsh-board / codex / generic>` | 只读导出 |
| `dsh push [--mode <cards 或 team>] [--dry-run]` | 投递到本机 DSH 看板；只建卡，不运行 |
| `dsh status` | 读回看板状态并与本地映射对照 |
| `dsh outcome <id> --result <succeeded 或 failed> --by <name>` | 把外部执行结果写回映射卡 |

通用参数：`--tickets` 指定票据目录（默认 `tickets`），`--root` 指定仓库根（默认当前目录）。

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
- `Acceptance` 至少一条 checkbox；`Verify` 必须能从仓库根目录复跑。

## DSH 看板适配

默认地址 `http://127.0.0.1:50567`，端口可用 `--url` 或 `DSH_TASK_BOARD_URL` 覆盖。

```bash
# 先看会创建哪些卡，不联网
python <技能目录>/scripts/dispatch.py dsh push --dry-run --json

# 创建卡片（只建卡，不运行）
python <技能目录>/scripts/dispatch.py dsh push --project <项目名>

# 团队模式：父卡 teamRun + 每票子卡
python <技能目录>/scripts/dispatch.py dsh push --mode team --project <项目名>
```

边界：

- `dsh push` 不运行卡；运行需要在 DSH 看板里由人确认，或显式调用看板的 `run` action。
- `dsh outcome` 写的是外部执行记录，不是本地验收结论。
- DSH 端点把 `record-external-outcome` 的 `summary` 写进 `execution.error` 字段，成功结果也如此；回读时以 `result=succeeded` 为准，不要用 `error` 是否存在判断失败。
- DSH HTTP 入口是本机插件接口，不是稳定公共 API；升级 DSH 后重跑一次真实投递探针。

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
- `verify` 在目标仓库根运行票据声明的命令；票据是受信任输入，但仍建议只给 L0/L1 自动执行。
- 写域检查基于 git diff 的规范化相对路径；symlink 越界是已知限制。
- L4 票据永远需要人工评审；不要用 `--human` 代替真实的人。
- 不要在票据里放真实凭据、私有绝对路径或生产密钥。

## 目录

- `SKILL.md`：本文件，技能入口。
- `src/agent_dispatch/`：自带框架；零运行时依赖。
- `scripts/dispatch.py`：从技能目录直接调用框架的包装器。
- `scripts/build_skill.py`：生成可复制的干净技能包（`dist/agent-dispatch-skill`）。
- `references/ticket-contract.md`：票据与回执契约细节。
- `references/dsh-board.md`：DSH 看板接口与实测边界。
- `references/codex-handoff.md`：Codex 工单交接方式。
- `templates/ticket.md`：最小票据模板。
