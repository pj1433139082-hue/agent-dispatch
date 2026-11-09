# 选型结论: dispatch-trust-boundaries

> 汇总各角色证据后填这张表；**结论由甲方签字才算过**（ADR-0007 Q1）。
>
> 产物模式：team（每份证据由独立子会话产出，文件头必须带 Persona 行）

| 角色 | 结论 | 证据位置 | 未证实项 |
|---|---|---|---|
| 开源借鉴侦察（oss-scout） | A/B/C 均建议采用（收敛形态） | 01-oss.md（152 行，commit 已钉） | continue 全仓标注、Claude Code 内部实现、SDK 逐行强制点、gstack 3败是否代码强制、BMAD/ruflo 未查、OpenHands V0 已 404 |
| 搜索取证（search-scout） | A/B/C 建议采用；「模型自评不能放行」绝对版**证据不足** | 02-sources.md（含 Lead 补证 U1 实测） | U2 网络边界官方不承诺、U3 精确版本号、U4 逐字禁令、U5 AutoGen 默认值；**U1 已由 Lead 实测解决** |
| 对抗性审查（adversary） | **建议不采用**（指按当前规格原样签字；最小修正后可转采用） | 03-adversary.md（54 行，7 条假设各配最小实验） | 看板是否真把 permission 落成沙箱、teammate 沙箱继承、围栏实际抑制幅度、重置/绕过行为频率 |

## 决策

- **采用**：A（不可信内容标注为数据）、B（工单带权限声明）、C（retry 有界）三个**方向**。三份证据一致支持，一手来源充足。
- **不采用**：文章里的 checks.md/progress.md/graph.md 三件套（dispatch 已有机器可读 receipt/verify/state）；花费/轮数上限（Q3，无计量能力会做成假门禁）；「模型自评一律不能放行」绝对版（Q2 + sources F4-4 存在 Codex auto_review 官方反例）。
- **暂不签字（打回回炉）**：adversary 7 条假设中 **6 条经 Lead 复核成立**，其中 4 条直接推翻已确认决策的字面形态：
  - 假设 1 → Q6 的 per-run cap + 复用 failed **实际无上界**（render/drop 归零 + failed 可派）
  - 假设 2 → Q5 的「按票收窄」在 team 路径被 `dsh.py:74` 取 max **放大**
  - 假设 3 → Q7 围栏范围**漏了 feedback-N.md 活通道**，且摘录**不转义**可逃逸
  - 假设 4/5 → trusted 入口可被合规种入；--force 报错**自带绕过命令**
- **已驳回 1 条**：假设 6（循环 import）经 Lead 实测不成立——`graph.py` 只 import `.ticket`，依赖链单向，`import agent_dispatch.cli` 正常。B 无需把 PERMISSIONS 搬出 export.py。
- **理由**：方向有据，但当前规格达不到声称的目标。**不为了推进而放宽检查**；4 个修正决策已写成第二轮前沿（A1-A4）落在 docs/questions/dispatch-trust-boundaries.md，**等用户回答后再签字**。

## 分歧与处置（详见 06-cross-review.md）

| 分歧 | 处置 |
|---|---|
| oss 建议 A 落点在 ENTRY_DOCS，但 Q4 定其 trusted、Q7 扩到 error | 以 Q4/Q7 为准；A 落点改为 error + feedback + 外部材料 |
| oss 建议 B「派发点强制」，但实测 subagent 无权限参数 | 以实测为准；subagent 路径只能声明并标注「未强制」 |
| oss 建议 C 超限置 blocked，Q6 定复用 failed | **待 A1 决策**；failed 可派是实测事实 |
| sources F2-1：三模式仅管文件系统 | Permission 段必须写明「不承诺网络/进程边界；Windows 可能 partial」 |
| adversary 假设 6 循环 import | **实测驳回**，原样输出见 06-cross-review.md |

## 甲方签字

- 签字人：lead
- 日期：2026-11-09
- 备注：三份证据齐备+交叉评审完成；adversary 6/7 成立且 4 条推翻已确认决策字面，A1-A4 待用户回答后回炉重签
- 选择：☐ 通过　☑ 有保留通过　☐ 打回
- 确认方式：card
