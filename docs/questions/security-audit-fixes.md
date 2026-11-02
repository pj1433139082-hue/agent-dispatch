# security-audit-fixes

**Purpose:** 把这次要做的事对齐到可以写规格的程度。

**From:** lead · **To:** 甲方 · **How your answers will be used:** 直接转成 spec 的输入。

## 这次要多细（先答这一条）

| 档位 | 问题数 | 适合 |
|---|---|---|
| quick | 3 | 已经想清楚，只确认卡点 |
| standard | 6 | 默认，功能需求 + 交付标准 |
| thorough | 10 | 跨团队 / 高风险 / 需要留证 |

> 当前档位：standard（6 问）。要换档，改这一行再发我即可。

## How to answer

10–20 分钟。没想好写「待定」并说明卡在哪；不确定就直说。

## 卡点

### 五个阶段里哪几处必须停下来等你签字？

_Why this matters: 决定自动化程度，也决定子 agent 什么时候能自己往前跑。_

> 签一次即可：本次 4+1 条修复同属一个交付批次，甲方在选型签字（已签）+ spec 确认（S3）两处停一次，票据执行阶段不再逐票找人。
## 交付标准

### 「交付标准」用什么形式锁定？

_Why this matters: 可命令化的验收命令是硬门禁，checkbox 用于人工核对。_

> 全部用可命令化的 `pytest` 断言锁定；人工 checkbox 只用于"文档口径已统一"这类无法自动判定的项。每条修复至少一条能在 CI 无网络环境跑通的 pytest。
## 授权

### 子 agent 可以自己做到哪一步？

_Why this matters: 只读 / 独立 worktree 写 / 可推分支，逐级放大风险。_

> 子 agent 只读审计 + 独立 worktree 内写；不推分支、不改 main、不删仓库外文件。D1 删除 `--from-commit` 属于破坏性变更，需在其票据的 brief 里显式写明并拿到批准。
## 证据

### 技术选型的最低证据要求是什么？

_Why this matters: 开源参照要指到具体文件或函数，并写明不采用的理由。_

> 本次不新做技术选型：证据已在 `docs/selection/security-audit-fixes/`（01-oss / 02-sources / 03-adversary / 06-cross-review）与 `docs/verification/2026-11-02-security-audit-findings.md`。票据只需引用它们的 fingerprint，不重复取证。
## 落点

### 问卷 / 规格 / 票据分别放在哪里？

_Why this matters: 决定别人能不能找到，也决定能不能复用。_

> 问卷 `docs/questions/`；选型证据 `docs/selection/security-audit-fixes/`；规格 `docs/specs/security-audit-fixes.md`；票据 `tickets/`；审计原文 `docs/verification/2026-11-02-security-audit-findings.md`。
## 失败处置

### 交付不合格时怎么处理？

_Why this matters: 回退上一阶段 / 就地补差 / 停下来问。_

> 就地补差，不跨阶段回退：某张票 verify 红则 `dispatch retry` 重做该票，不动已绿的其他票。若发现根因判断错误（如 D2 的真旁路定位不对），停下并回 grill 阶段重开一轮，不许在票里临时发明新需求。
## Anything else?

还有什么没问到但会影响落地的？

> 三处文档矛盾（C1/C3/C4）必须在同一批修掉，否则 spec 自相矛盾：C3 给 ADR-0017 补 Status: Superseded；C1 以代码为准改 SKILL.md:345；C4 以 ticket-contract:79 为准改 SKILL.md:666。另：D4（export.py:39-42 票面自述 done）是交叉评审新发现，与 D2 同批处理。