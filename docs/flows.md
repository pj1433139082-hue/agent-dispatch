# 流程地图：四条流程、命令衔接、与其它技能的交界

> 一页看清 agent-dispatch 到底跑哪几条流程、每条用什么命令串起来、上下游是谁。
> 细节以 `SKILL.md` 与 `docs/adr/` 为准。

## 0. 一句话

`dispatch` 只做**契约与证据**：把"要做什么"翻译成一份可验收的工单，把"谁做、改了哪、拿什么证据"冻结下来，最后用独立门禁放行。
**它不创建 agent**，也不跑模型。

---

## 1. 四条流程

### 流程 A｜需求 → 规格 → 票（S1–S5，ADR-0007）

用途：一个模糊需求，变成一叠可执行票。

`@
align <slug> --level quick|standard|deep      # S1 生成问卷
  → （人答问卷 / stage --prompt 弹窗）
select <slug>                                  # S2 选型包（oss-scout / search-scout / adversary）
sign <slug> --by <人> --via dialog|card        # S2 签字（不签不给 spec）
spec <slug>                                    # S3 规格骨架
confirm <slug> --by <人> --via dialog|card      # S3 交付标准已核对
tickets <slug>                                 # S4 拆票 → .dispatch/drafts/<slug>/
  → 人工补 Write scope / Verify → 挪进 tickets/ → lint
stage <slug> [--json] [--prompt]               # 任何时刻看卡在哪、下一步是什么
`@

配套：`stage --prompt` 输出结构化问题，喂给 `ask_user_question` 或决策卡；`--via` 强制留痕。

### 流程 B｜单票执行（主流程）

`@
lint → plan                      # 校验 + 分波（同波写域冲突会报）
brief <id>                       # 只读 brief（理解/计划/要改的文件/风险/疑问）
brief <id> --approve <人>        # 人审通过
render <id> --agent <name>       # 建 run + worktree + work-order.md（票据 → claimed）
handoff <id> [--to <agent>]      # 打印"该发给谁、发什么"
start <id>                       # claimed → running
verify <id>                      # 独立验收：passed / degraded / failed
review <id> --reviewer <另一人>   # 异体评审（L4 加 --human；degraded 加 --accept-degraded）
land <id>                        # 只建 integration branch，不 push、不合并目标
closeout <id>                    # 收口报告（可选，--require-closeout 时必需）
`@

失败语义：verify 失败 → 票 `failed` → `retry <id> --reason …` 回 `running` 再验；
review 拒绝 → 修完重新 verify + review。

### 流程 C｜批量与自动

`@
auto <id> --executor "<cmd>" [--max-attempts N] [--until review|land]
land --wave [--json] [--continue-on-error]
`@

- `auto` 是**单票推进器**：开跑前体检（索引/磁盘不一致直接拒），失败把 findings 写 `auto/feedback-<n>.md` 回灌下一次。
- `--until land` 会先生成 `review-packet.md`，reviewer 通过 `DISPATCH_REVIEW_PACKET` 拿到冻结输入并回填 `packet_hash`。
- `land --wave` 按**拓扑序**批量落地，跳过未完成/已落地并说明原因。
- 纪律：**一次一票**，别把整波塞进一个上下文（实测 5.4M tokens 会炸）。

### 流程 D｜运维与恢复

`@
doctor [--json] [--fix]     # 体检：票 / 索引 / 失败 / 超期 / 租约；--fix 只做安全修复
sweep                       # 只读巡检：哪些 run 还活着、是否超期
repair [--write]            # 索引以磁盘为准重建；冲突不覆盖
claim <id> / release <id>   # 文件租约：占写域 / 放锁
gc [--apply]                # 回收已结束 run 的 worktree
retry <id> --reason …       # failed → running
`@

---

## 2. 命令衔接（谁产出、谁消费）

| 产出 | 由谁 | 谁消费 |
|---|---|---|
| 问卷 `docs/questions/<slug>.md` | `align` | 人 / 弹窗 |
| 选型包 `docs/selection/<slug>/` | `select` | `sign` → `spec` |
| 规格 `docs/specs/<slug>.md` | `spec` | `confirm` → `tickets` |
| 草稿票 `.dispatch/drafts/<slug>/` | `tickets` | 人补齐 → `tickets/` → `lint` |
| Run + worktree + `work-order.md` | `render` | 执行端（teammate / 看板 / 命令） |
| `receipt.json` + 证据 | 执行端 | `verify` |
| `verify.json` | `verify` | `review` / `closeout` / `land` |
| `review-packet.md` | `auto` / `review-packet` | reviewer |
| `review.json` | `review` | `land` |
| `landing.json` | `land` | `status` / `doctor` |

---

## 3. 与其它技能的交界

| 上游技能 | 它给 dispatch 什么 | 衔接命令 |
|---|---|---|
| `ask-matt` | 决定"做不做、先后" | 结论落成 slug 后 `align` |
| `grill-with-docs` / `grilling` | 方案与取舍，产出 ADR / 术语 | 方案定了 → `spec` / `to-spec` |
| `to-spec` | 一份规格 | 放进 `docs/specs/` → `confirm` → `tickets` |
| `to-tickets` | 一叠带阻塞关系的票 | 放进 `tickets/` → `lint` → `plan` |
| `implement` / `implement-spec` | 真正的实现动作 | 由 `render` 出工作单后交给它 |
| `tdd` | 红→绿实现纪律 | 票的 `Verify` 就是它的红灯 |
| `verification` | "不许空口说完成" | 就是 `verify` 的哲学 |
| `code-review` | 两轴评审 | `review` 的 `--reviewer` 可以就是它 |
| `diagnosing-bugs` | 找根因 | 票修好后走 `retry` |
| `pr` | 写 PR 正文 | `land` 产出 integration branch 后用它 |
| `handoff` | 会话交接 | 交接里带 `dispatch status` + `stage` 输出 |
| `retro` | 复盘 | 输入是 `dispatch status` / `landing.json` |

下游：`land` 只建分支不 push；开 PR、合并、部署交给 `pr` / `design-web-release` 这类技能或人。

---

## 4. 三条执行端（dispatch 不创建 agent）

1. **teammate**：`handoff <id> --to <agent>` → `send_message` → 它交 brief → 批准 → 在 worktree 干 → `verify` → 另一人 `review`。
   `render --agent X` 只是把名字写进工作单，**不会创建 teammate**。
2. **DSH 看板**：`dsh push --project <p>` 建卡 → 人在板上点 run → `dsh outcome` 回写（看板 `127.0.0.1:62407`）。
3. **外部执行器**：`auto <id> --executor "<cmd>"`；没有 teammate 时这条等同主代理自执行，要如实标注。
