# GLOSSARY · agent-dispatch

> 只收"用错就会出事"的词。每个词给：定义 / 不算什么 / 判据。

## 票（ticket）
- **定义**：一个可独立验收的交付单元，含 Owner / Risk / Write scope / Verify / Acceptance。
- **不算**：任务清单里的一行；没有 Verify 的"要做的事"不是票。
- **判据**：`lint` 通过且能 `render` 出 run。

## 判据（criterion）与验收项（acceptance item）
- **判据**：`receipt.criteria[n]`，带证据（file / inline / command / note），回答"这一条凭什么算完成"。
- **验收项**：票面 `- [ ]` 那一行，回答"要交付什么"。
- **关系**：一一对应，`criteria` 的 id 必须正好 `1..N`（N = 验收项条数）。

## 执行根（execution root）
- **定义**：run 真正写文件的地方。默认是 `.dispatch/worktrees/<run-id>`；`--no-worktree` 时就是仓库根。
- **不算**：run 目录（`.dispatch/runs/<run-id>`）——那是证据目录，不是干活的地方。

## 快照判据（snapshot criterion）
- **定义**：Verify 不断言远端/在线事实，只断言一份带时间戳的本地快照。
- **不算**：把远端输出粘进票面（不可复跑）。

## 重复失败指纹（failure fingerprint）
- **定义**：`verify-history.jsonl` 里同一组错误文本的连续出现次数。
- **用途**：第 3 次起提示"再跑没用"，把问题从"再试一次"推向"改环境或改判据"。

## 落地区间（integration branch）
- **定义**：`land` 建出的 `dispatch/land/<run-id>` 分支，聚合已验收的票。
- **不算**：main；`land` 从不 push、不合并 main。

## 合后全量回归（verify-all）
- **定义**：`land --verify-all "<命令>"` 在 integration branch 上跑的一整套回归命令（如 `python -m pytest -q`），回答"这条分支合起来还能不能用"。
- **不算**：票面 `Verify`（那只证明这一张票的命令能跑）、`--append` 累积本身。
- **判据**：`landing.json.verify_all_status == "pass"`；失败时 `status` 是 `landed-unverified`，退出码 1。

## 人格（persona）
- **定义**：一张角色卡（`agents/personas/*.md`：role / domain / capabilities / forbidden_actions），是**执行端的输入**，不是执行者本身。
- **不算**：被 spawn 的 teammate（那是执行者）、票面 Owner（那是责任人）、票面 `- Persona:` 字符串（那只是指向角色卡的指针）。
- **判据**：说得出这次执行用的是哪张角色卡，并能核对它没有在事后被改过。

## 决策票（decision ticket）
- **定义**：一张只回答"选哪个方向"的票，写清问题 / 选项 / 判据 / 截止。
- **不算**：执行票（执行票有 Write scope / Verify，进 `plan` 波次）、spec（spec 是整份交付的合同）。
- **判据**：读完能拍一个方向，且不需要写代码。

## 执行票（execution ticket）
- **定义**：方向已定、只差动手的票：`tickets/NN-slug.md`，带 Owner / Risk / Write scope / Verify / Acceptance。
- **不算**：决策票（只问方向）、草稿（`.dispatch/drafts/` 里还没补契约的）。
- **判据**：`lint` 过、`plan` 能排进波次、`render` 能开 run。

## 阶段边界（phase boundary）
- **定义**：一个会话里两块活之间的缝（grilling → 实现、实现 → 验收）；只在这里决定 continue / clear / handoff / subagent / compact。
- **不算**：阶段中间（那里只有"继续"或"拆子任务"，压缩会丢线索）。
- **判据**：说得出下一阶段需不需要这一阶段的**原始上下文**。

## 出界知识库（out-of-scope knowledge base）
- **定义**：仓库根 `.out-of-scope/<概念>.md`，记录被否掉的方向、理由与历史请求，一个概念一个文件。
- **不算**：run 失败记录（那是 `dispatch drop --reason` 与 ledger 的事）。
- **判据**：下次有人再提同一方向，能先翻到这一页而不是重新论证。
## 收口（wrap-up）
- **定义**：`dispatch wrap` 一次性给出"这轮活干完没有"：失败票、超期 run、未落地 run、会挡 land 的脏文件、过期租约。
- **判据**：`wrap` exit 0 才算收工；exit 1 表示还有事没处理。

## 职能队友（functional teammate）
- **定义**：按"环节"划分的常驻队友（scout/planner/executor/verifier/reviewer/auditor/fixer/scribe），能接任何项目的同类任务。
- **不算**：领域人格（Agency Agents 那种 "Frontend Developer"）；领域人格只能干一类活。

## fresh 实例（fresh instance）
- **定义**：`spawn_teammate({context:"fresh"})` 起来的一次性队友，没有 Lead 历史，任务完即删。
- **用途**：重活、需要无偏见判断的活；避免常驻成员的上下文腐烂。

## 手账分离（hands vs ledger）
- **定义**：teammate 是"手"（产出改动与证据），`dispatch` 是"账"（票状态、verify、review、land）。
- **判据**：任何 teammate 都不写 `receipt.json`/`state.json`；写了的，一律判越界。

## roster（成员表）
- **定义**：一支团队里已创建的 teammate 名单；**只增不减**，名字永久占用（官方文档原文：创建失败的 teammate 也保留名字）。
- **判据**：`list_agents` 返回的成员数 = roster 大小；`maxMembers` 是上限（官方 profile 配 8，基础包默认 16）。
- **可删**：官方无删除能力；装 `dsh-agent-team-roster` 插件后有 `delete_teammate`（删记录 + 释放名字）与 `rename_teammate`（改名保历史）。
