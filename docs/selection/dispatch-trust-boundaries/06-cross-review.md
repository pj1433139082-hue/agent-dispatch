# 交叉评审: dispatch-trust-boundaries

评审日期：2026-11-08（Lead）+ 子智能体 adversary（见下方追加）。
规则：本轮只读，不改三份证据本身；分歧由 Lead 汇总后回填 99-summary。

## Lead 交叉核对（读 01/02 后自己发现的分歧）

### R1 — 质疑对象：01-oss.md 的 A 落点建议
反驳：oss 建议「context.py **ENTRY_DOCS** 摘录块加来源标注 + 数据声明」，但用户 Q4 已定 ENTRY_DOCS（AGENTS/CLAUDE/CONTEXT）为 **trusted 指令源**，保持指令地位；Q7 又把围栏范围扩到**前序 run 的 auto.json.error**。oss 的落点指错了对象。
依据：docs/questions/dispatch-trust-boundaries.md Q4/Q7；context.py:156-164（ENTRY_DOCS 摘录）vs :175-176（error 摘录）。
要求补的证据：把 A 的落点改为「error 字段 + 未来任何外部材料摘录点」，并说明 ENTRY_DOCS 为何不加围栏（DSH 自身也加载它们作为指令）。

### R2 — 质疑对象：01-oss.md 的 B 落点建议
反驳：oss 建议「render 时传给执行端宿主的沙箱/工具规则」，并引 OpenHands `scope_delegation_tools` 作证。但本机实测：`subagent` 签名只有 {cwd?, description, prompt}，`spawn_teammate` 只有 {name, description, prompt, context?}，**都不接受权限参数**；5/5 子会话继承父会话 danger-full-access。该建议在 subagent/teammate 路径**不可行**。
依据：02-sources.md「Lead 补证：U1 已在本机实测解决」；Object.keys(tools) + 工具签名核对。
要求补的证据：B 必须区分两条路径——DSH 看板（dsh.py 已传 permission，可强制）与 subagent/teammate（无参数，只能声明并标注「未强制」）。不得把 OpenHands 的工具层强制说成 dispatch 也能做到。

### R3 — 质疑对象：02-sources.md 的 F2-1 语义边界
反驳：sources 正确指出 DSH 三模式「仅管文件系统，网络与进程不在定义范围内」。但 01-oss.md 的 B 结论把 PERMISSIONS 当作通用「权限约束」推荐，未提这个限定。若 dispatch 文档把 workspace-write 宣传成「网络也被管住」，就是超出官方语义的误导。
依据：02-sources.md F2-1 原文摘录；export.py:11 PERMISSIONS 定义无任何注释说明边界。
要求补的证据：workorder 的 Permission 段必须写明「仅文件系统效果；不承诺网络/进程边界；Windows 可能 partial」。

## 子智能体 adversary 的质疑（待追加）

子智能体 `f8e561e7`（adversary）已产出 03-adversary.md（54 行，7 条假设，结论「建议不采用（按当前规格原样签字）」）。
Lead 逐条复核如下——**成立 6 条，驳回 1 条**。

| # | adversary 主张 | Lead 复核 | 判定 |
|---|---|---|---|
| 1 | C 的 attempt 挂 run 上，render/drop 后归零；failed 可派 → 编排无上界 | `cli.py:1182-1189` 对 failed 不拒（ACTIVE_STATES={claimed,running,review}，`state.py:17`）；`export.py:24-25` `_dispatchable` 含 failed；`lifecycle.py:164` drop 删索引 | **成立**，且比 Q6 设想严重 |
| 2 | team 父卡取全波最高风险 → 同波低风险票被放大权限 | `dsh.py:74` `max(risks, key=RISK_ORDER)`，`:168` 传全票 risk 列表 | **成立**（代码确凿） |
| 3 | 围栏不转义可被 ``` 提前闭合；feedback-N.md 是另一条未围栏活通道 | `context.py:164` 用 ```text 包原文无转义；`feedback.py:28` 逐条原样拼；`auto.py:403-416` 经 DISPATCH_FEEDBACK 指给执行器 | **成立**，Q7 范围漏了 feedback |
| 4 | 入口文档 trusted 无依据：write_scope 含 AGENTS.md 的票可合规种指令 | `setup-agent-dispatch` 流程本身写目标仓 AGENTS.md；verify 只查 diff-vs-scope | **成立**（跨仓尤甚） |
| 5 | --force 无鉴权，报错提示自带绕过命令 → agent 自学绕过 | `cli.py:2156-2237` 无交互确认；`--reason` 虽必填但机器可填 | **成立** |
| 6 | workorder 导入 export.PERMISSIONS 会成环，全 CLI 起不来 | **实测驳回**：`graph.py` 只 `from .ticket import Ticket`，**不 import workorder**。依赖链 export→graph→ticket 单向；workorder→persona/ticket。实测 `import agent_dispatch.cli` 正常，PERMISSIONS 可读 | **不成立** |
| 7 | 证据结论与决策错位（oss 说 blocked，Q6 定 failed；oss 说派发点强制，Q5 只剩正文） | 并读 01-oss:143 与 Q6、01-oss:83/142 与 Q5，确实偏离且未记录 | **成立** |

**驳回 6 的实测原样输出**：
```
graph imports workorder? False
export.PERMISSIONS: {'L0': 'read-only', 'L1': 'workspace-write', ...}
workorder loaded OK
graph -> ['from .ticket import Ticket']
export -> ['from .graph import build_plan', 'from .persona import persona_section', 'from .ticket import Ticket']
workorder -> ['from .persona import persona_section', 'from .ticket import Ticket']
```
所以 B **不必**把 PERMISSIONS 搬出 export.py，写域无需扩到 graph.py。但假设 1/2/3/5 成立，方案确实要回炉。
